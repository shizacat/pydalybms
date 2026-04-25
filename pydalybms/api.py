"""
The library for Daly BMS UART
"""

from __future__ import annotations

from pathlib import Path

import serial

from .models import (
    BatteryFailureStatusAnswer,
    CellVoltagesAnswer,
    SoCAnswer,
    StatusInformation1Answer,
    TemperatureMinMaxCellAnswer,
    VoltageMinMaxCellAnswer,
)
from .frame import DalyBMSResponseFrame, DalyBMSCommand, DalyBMSHostAddress


class DalyBMS:

    # Default UART configuration for Daly BMS
    # - Baud rate: 9600
    # - Data bits: 8
    # - Parity: None
    # - Stop bits: 1
    DEFAULT_BAUD = 9600
    DEFAULT_BITS = serial.EIGHTBITS
    DEFAULT_PARITY = serial.PARITY_NONE
    DEFAULT_STOPBITS = serial.STOPBITS_ONE

    # Length of the response from the Daly BMS
    RESPONSE_LEN = 13  # 12 + CRC

    def __init__(
        self,
        device_path: str,
        timeout: float = 0.5,
        host_address: DalyBMSHostAddress = DalyBMSHostAddress.PC,
    ):
        """
        Initialize the Daly BMS API.

        Args:
            device_path: The path to UART device on host
            timeout: The timeout for the serial connection
            host_address: Host address for Daly BMS

        Raises:
            FileNotFoundError: If the device path does not exist
            IsADirectoryError: If the path is a directory (not a serial device)
        """
        self._device_path: str = device_path
        self._host_address: DalyBMSHostAddress = host_address

        self._checks()

        # Initialize the serial connection
        self._serial = serial.Serial(
            port=self._device_path,
            baudrate=self.DEFAULT_BAUD,
            bytesize=self.DEFAULT_BITS,
            parity=self.DEFAULT_PARITY,
            stopbits=self.DEFAULT_STOPBITS,
            timeout=timeout,
        )

    # --- Private methods ---

    def _checks(self) -> None:
        """Existing path and not a directory (serial devices are not regular files)."""
        device_path = Path(self._device_path)
        if not device_path.exists():
            raise FileNotFoundError(f"Device path {self._device_path} does not exist")
        if device_path.is_dir():
            raise IsADirectoryError(
                f"Device path {self._device_path} is a directory, not a serial port"
            )

    def _build_read_frame(self, host_address: int, command: int) -> bytes:
        """
        Build the read frame for the Daly BMS

        Frame format:
            12 bytes + CRC:
                - Start Flag, 0xA5 (Fixed)
                - PC address, (nibble<<4) as UPPER-ADD
                - Data ID, command
                - Data length, 0x08 (Fixed)
                - Data content, 8 bytes
                - Checksum, CRC

        Args:
            host_address: The host address nibble (0..15) by §2.2
                - 4 → 0x40 (Upper computer)
                - 8 → 0x80 (Bluetooth)
            command: The command to send
                - 0x90: Get SOC
                - 0x91: Get temperature
                - 0x92: Get voltage
                - 0x93: Get current
                - 0x94: Get power
                - 0x95: Get capacity
                - 0x96: Get cycle count
                - 0x97: Get health

        Raises:
            ValueError: If the host address nibble is wrong

        Returns:
            The read frame, bytes, 12 bytes + CRC
        """
        if not (0 <= host_address <= 15):
            raise ValueError("host_address_nibble 0..15")
        frame = bytearray(12)
        frame[0] = 0xA5
        frame[1] = (host_address & 0x0F) << 4
        frame[2] = command
        frame[3] = 0x08
        crc = self._daly_crc12(bytes(frame))
        return bytes(frame) + bytes([crc])

    def _daly_crc12(self, message_without_crc: bytes) -> int:
        """
        Calculate the CRC12 for the Daly BMS

        Args:
            message_without_crc: The message without the CRC

        Returns:
            The CRC12, int
        """
        return sum(message_without_crc) & 0xFF

    def _read_one_frame(self) -> bytes:
        """
        Read one frame from serial port
        Serial port must be opened

        Returns:
            The response from the serial port, DalyBMSResponseFrame

        Raises:
            ValueError: If the response is invalid
            SerialException: If the serial port is not available
        """
        # Read the response from the serial port
        response = self._serial.read(self.RESPONSE_LEN)
        # Check if the response is valid
        if len(response) != self.RESPONSE_LEN:
            raise ValueError(f"Invalid response length: {len(response)}")
        # Check if the response is valid
        if response[0] != 0xA5:
            raise ValueError("Invalid response start flag")
        # Check if the CRC is valid
        if self._daly_crc12(response[:-1]) != response[-1]:
            raise ValueError("Invalid response CRC")
        return response

    def _send_frame_and_read_one_raw(self, frame: bytes) -> bytes:
        """
        Send frame and read one frame from the Daly BMS

        Args:
            frame: The frame to send

        Returns:
            The response from the Daly BMS, bytes

        Raises:
            ValueError: If the response is invalid
            SerialException: If the serial port is not available
        """
        # Write the frame to the serial port
        with self._serial:
            # Reset the input and output buffers
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()

            # Write the frame to the serial port
            self._serial.write(frame)

            # Read one frame from serial port
            return self._read_one_frame()

    def _send_frame_and_read_one(self, frame: bytes) -> DalyBMSResponseFrame:
        """
        Send frame and read one frame from the Daly BMS
        """
        return DalyBMSResponseFrame.from_bytes(self._send_frame_and_read_one_raw(frame))

    def _send_frame_and_read_muliti(
        self, frame: bytes, frames_count: int
    ) -> list[DalyBMSResponseFrame]:
        """
        Read multiple frames from serial port
        Serial port must be opened
        """
        frames: list[DalyBMSResponseFrame] = []

        # Write the frame to the serial port
        with self._serial:
            # Reset the input and output buffers
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()

            # Write the frame to the serial port
            self._serial.write(frame)

            for _ in range(frames_count):
                frames.append(DalyBMSResponseFrame.from_bytes(self._read_one_frame()))
        return frames

    # --- Public methods ---

    def get_soc(self) -> SoCAnswer:
        """
        SOC, voltages, and current (0x90).

        Byte0~1 cumulative U (0.1 V); 2~3 gather U; 4~5 current (30000 offset, 0.1 A);
        6~7 SOC (0.1 %).
        """
        frame = self._send_frame_and_read_one(
            self._build_read_frame(
                host_address=DalyBMSHostAddress.PC.value,
                command=DalyBMSCommand.SOC.value,
            )
        )
        return SoCAnswer.from_frame(frame)

    def get_voltage_min_max_cell(self) -> VoltageMinMaxCellAnswer:
        """
        Return the number of cell with voltage min and max.
        """
        frame = self._send_frame_and_read_one(
            self._build_read_frame(
                host_address=DalyBMSHostAddress.PC.value,
                command=DalyBMSCommand.VOLTAGE_MIN_MAX.value,
            )
        )
        return VoltageMinMaxCellAnswer.from_frame(frame)

    def get_temperature_min_max_cell(self) -> TemperatureMinMaxCellAnswer:
        """
        Return the number of cell with temperature min and max.
        """
        frame = self._send_frame_and_read_one(
            self._build_read_frame(
                host_address=DalyBMSHostAddress.PC.value,
                command=DalyBMSCommand.TEMPERATURE_MIN_MAX.value,
            )
        )
        return TemperatureMinMaxCellAnswer.from_frame(frame)

    def get_status_information(self) -> StatusInformation1Answer:
        """
        Return status information 1
        """
        frame = self._send_frame_and_read_one(
            self._build_read_frame(
                host_address=DalyBMSHostAddress.PC.value,
                command=DalyBMSCommand.STATUS_1.value,
            )
        )
        return StatusInformation1Answer.from_frame(frame)

    def get_battery_failure_status(self) -> BatteryFailureStatusAnswer:
        """
        Battery failure status (0x98), §3.
        """
        frame = self._send_frame_and_read_one(
            self._build_read_frame(
                host_address=DalyBMSHostAddress.PC.value,
                command=DalyBMSCommand.FAULT.value,
            )
        )
        return BatteryFailureStatusAnswer.from_frame(frame)

    def get_cell_voltages(self, cell_count: int = 48) -> CellVoltagesAnswer:
        """
        Cell voltage 1~48 (0x95), §3.

        Daly returns multiple response frames after a single request; each frame contains
        voltages for up to 3 cells (mV, big-endian) plus a frame counter byte.
        """
        # Calculate frames count
        frames_count = (cell_count + 2) // 3

        frames: list[DalyBMSResponseFrame] = self._send_frame_and_read_muliti(
            self._build_read_frame(
                host_address=DalyBMSHostAddress.PC.value,
                command=DalyBMSCommand.CELL_V.value,
            ),
            frames_count=frames_count,
        )

        return CellVoltagesAnswer.from_frames(frames, cell_count=cell_count)
