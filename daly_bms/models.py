"""
Models for Daly BMS
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .frame import DalyBMSResponseFrame


def _doc(s: str) -> dict:
    return {"description": s}


@dataclass
class VoltageCell:
    """
    Voltage in one cell
    """

    voltage: float = field(metadata=_doc("Voltage, V. Напряжение, В."))
    number: int = field(metadata=_doc("Number, int. Номер ячейки."))


@dataclass
class TemperatureCell:
    """
    Temperature in one cell
    """

    temperature: float = field(metadata=_doc("Temperature, C. Температура, С."))
    number: int = field(metadata=_doc("Number, int. Номер ячейки."))


# --- Classes Answers ---


@dataclass
class SoCAnswer:
    """
    Ответ на запрос SOC
    """

    cumulative_total_voltage: float = field(
        metadata=_doc(
            "Cumulative total voltage, V. "
            "Суммарное напряжение по ячейкам (см. даташит Daly 0x90)."
        )
    )
    gather_total_voltage: float = field(
        metadata=_doc(
            "Gather total voltage, V. "
            "Второй канал измерения U пачки (см. даташит Daly 0x90)."
        )
    )
    current: float = field(
        metadata=_doc("Current, A. Ток, А (смещение 30000 в сырых данных BMS).")
    )
    soc: float = field(metadata=_doc("State of Charge (SOC), %. Состояние заряда, %."))

    @classmethod
    def from_frame(cls, frame: DalyBMSResponseFrame) -> "SoCAnswer":
        """
        Parse SoC answer from Daly BMS response frame.

        Byte0~Byte1:Cumulative total voltage (0.1 V)
        Byte2~Byte3:Gather total voltage (0.1 V)
        Byte4~Byte5:Current (30000 Offset ,0.1A)
        Byte6~Byte7:SOC (0.1%)

        Args:
            frame: Daly BMS response frame.

        Returns:
            SoC answer.
        """
        # §3 / 0x90: значения напряжения и SOC — беззнаковые 16-bit; ток кодируется offset=30000.
        cumul_raw = struct.unpack(">H", frame.data[0:2])[0]
        gather_raw = struct.unpack(">H", frame.data[2:4])[0]
        current_raw = struct.unpack(">H", frame.data[4:6])[0]
        soc_raw = struct.unpack(">H", frame.data[6:8])[0]
        return SoCAnswer(
            cumulative_total_voltage=cumul_raw / 10.0,
            gather_total_voltage=gather_raw / 10.0,
            current=(current_raw - 30000) / 10.0,
            soc=soc_raw / 10.0,
        )


@dataclass
class VoltageMinMaxCellAnswer:
    """
    Cell with voltage min and max
    """

    min: VoltageCell = field(metadata=_doc("Min voltage cell."))
    max: VoltageCell = field(metadata=_doc("Max voltage cell."))

    @classmethod
    def from_frame(cls, frame: DalyBMSResponseFrame) -> "VoltageMinMaxCellAnswer":
        """
        Parse VoltageMinMaxCellAnswer from Daly BMS response frame.

        Byte0~Byte1:Maximum cell voltage value (mV)
        Byte2:No of cell with Maximum voltage
        Byte3~byte4: Minimum cell voltage value (mV)
        Byte5:No of cell with Minimum voltage

        Args:
            frame: Daly BMS response frame.

        Returns:
            VoltageMinMaxCellAnswer.
        """
        # §3 / 0x91: сначала MAX (mV), потом MIN (mV). Значения — беззнаковые 16-bit.
        max_mv = struct.unpack(">H", frame.data[0:2])[0]
        max_no = struct.unpack(">B", frame.data[2:3])[0]
        min_mv = struct.unpack(">H", frame.data[3:5])[0]
        min_no = struct.unpack(">B", frame.data[5:6])[0]

        return VoltageMinMaxCellAnswer(
            min=VoltageCell(voltage=min_mv / 1000.0, number=min_no),
            max=VoltageCell(voltage=max_mv / 1000.0, number=max_no),
        )


@dataclass
class TemperatureMinMaxCellAnswer:
    """
    Cell with temperature min and max
    """

    min: TemperatureCell = field(metadata=_doc("Min temperature cell."))
    max: TemperatureCell = field(metadata=_doc("Max temperature cell."))

    @classmethod
    def from_frame(cls, frame: DalyBMSResponseFrame) -> "TemperatureMinMaxCellAnswer":
        """
        Parse TemperatureMinMaxCellAnswer from Daly BMS response frame.

        Byte0: Maximum temperature value (40 Offset ,°C)
        Byte1: Maximum temperature cell No
        Byte2: Minimum temperature value (40 Offset ,°C)
        Byte3: Minimum temperature cell No

        Args:
            frame: Daly BMS response frame.
        """
        # В даташите для 0x92 используются 1-байтовые значения (offset 40), не int16.
        max_temp_c = float(frame.data[0] - 40)
        max_no = int(frame.data[1])
        min_temp_c = float(frame.data[2] - 40)
        min_no = int(frame.data[3])

        return TemperatureMinMaxCellAnswer(
            min=TemperatureCell(temperature=min_temp_c, number=min_no),
            max=TemperatureCell(temperature=max_temp_c, number=max_no),
        )


@dataclass
class StatusInformation1Answer:
    """
    Status information 1 (Data ID 0x94), §3.

    Byte0: No of battery string (cells count)
    Byte1: No of Temperature (temperature sensors count)
    Byte2: Charger status (0 disconnect, 1 access)
    Byte3: Load status (0 disconnect, 1 access)
    Byte4: DI/DO bits (bit0..3 DI1..DI4, bit4..7 DO1..DO4)
    Byte5~Byte7: Reserved
    """

    cells: int = field(metadata=_doc("Number of cells (battery strings)."))
    temperature_sensors: int = field(metadata=_doc("Number of temperature sensors."))
    charger_connected: bool = field(
        metadata=_doc("Charger status: True if access/connected.")
    )
    load_connected: bool = field(
        metadata=_doc("Load status: True if access/connected.")
    )
    di1: bool = field(metadata=_doc("DI1 state (Byte4 bit0)."))
    di2: bool = field(metadata=_doc("DI2 state (Byte4 bit1)."))
    di3: bool = field(metadata=_doc("DI3 state (Byte4 bit2)."))
    di4: bool = field(metadata=_doc("DI4 state (Byte4 bit3)."))
    do1: bool = field(metadata=_doc("DO1 state (Byte4 bit4)."))
    do2: bool = field(metadata=_doc("DO2 state (Byte4 bit5)."))
    do3: bool = field(metadata=_doc("DO3 state (Byte4 bit6)."))
    do4: bool = field(metadata=_doc("DO4 state (Byte4 bit7)."))

    @classmethod
    def from_frame(cls, frame: DalyBMSResponseFrame) -> "StatusInformation1Answer":
        b0 = int(frame.data[0])
        b1 = int(frame.data[1])
        b2 = int(frame.data[2])
        b3 = int(frame.data[3])
        b4 = int(frame.data[4])

        def bit(n: int) -> bool:
            return bool((b4 >> n) & 0x01)

        return StatusInformation1Answer(
            cells=b0,
            temperature_sensors=b1,
            charger_connected=bool(b2),
            load_connected=bool(b3),
            di1=bit(0),
            di2=bit(1),
            di3=bit(2),
            di4=bit(3),
            do1=bit(4),
            do2=bit(5),
            do3=bit(6),
            do4=bit(7),
        )


@dataclass
class BatteryFailureStatusAnswer:
    """
    Battery failure status (Data ID 0x98), §3.

    Payload: 8 bytes where Byte0..Byte6 are bitfields (0 normal, 1 fault),
    Byte7 is a fault code.
    """

    # Byte0
    cell_volt_high_level_1: bool = field(metadata=_doc("Byte0 bit0"))
    cell_volt_high_level_2: bool = field(metadata=_doc("Byte0 bit1"))
    cell_volt_low_level_1: bool = field(metadata=_doc("Byte0 bit2"))
    cell_volt_low_level_2: bool = field(metadata=_doc("Byte0 bit3"))
    sum_volt_high_level_1: bool = field(metadata=_doc("Byte0 bit4"))
    sum_volt_high_level_2: bool = field(metadata=_doc("Byte0 bit5"))
    sum_volt_low_level_1: bool = field(metadata=_doc("Byte0 bit6"))
    sum_volt_low_level_2: bool = field(metadata=_doc("Byte0 bit7"))

    # Byte1
    chg_temp_high_level_1: bool = field(metadata=_doc("Byte1 bit0"))
    chg_temp_high_level_2: bool = field(metadata=_doc("Byte1 bit1"))
    chg_temp_low_level_1: bool = field(metadata=_doc("Byte1 bit2"))
    chg_temp_low_level_2: bool = field(metadata=_doc("Byte1 bit3"))
    dischg_temp_high_level_1: bool = field(metadata=_doc("Byte1 bit4"))
    dischg_temp_high_level_2: bool = field(metadata=_doc("Byte1 bit5"))
    dischg_temp_low_level_1: bool = field(metadata=_doc("Byte1 bit6"))
    dischg_temp_low_level_2: bool = field(metadata=_doc("Byte1 bit7"))

    # Byte2
    chg_overcurrent_level_1: bool = field(metadata=_doc("Byte2 bit0"))
    chg_overcurrent_level_2: bool = field(metadata=_doc("Byte2 bit1"))
    dischg_overcurrent_level_1: bool = field(metadata=_doc("Byte2 bit2"))
    dischg_overcurrent_level_2: bool = field(metadata=_doc("Byte2 bit3"))
    soc_high_level_1: bool = field(metadata=_doc("Byte2 bit4"))
    soc_high_level_2: bool = field(metadata=_doc("Byte2 bit5"))
    soc_low_level_1: bool = field(metadata=_doc("Byte2 bit6"))
    soc_low_level_2: bool = field(metadata=_doc("Byte2 bit7"))

    # Byte3
    diff_volt_level_1: bool = field(metadata=_doc("Byte3 bit0"))
    diff_volt_level_2: bool = field(metadata=_doc("Byte3 bit1"))
    diff_temp_level_1: bool = field(metadata=_doc("Byte3 bit2"))
    diff_temp_level_2: bool = field(metadata=_doc("Byte3 bit3"))

    # Byte4
    chg_mos_temp_high_alarm: bool = field(metadata=_doc("Byte4 bit0"))
    dischg_mos_temp_high_alarm: bool = field(metadata=_doc("Byte4 bit1"))
    chg_mos_temp_sensor_err: bool = field(metadata=_doc("Byte4 bit2"))
    dischg_mos_temp_sensor_err: bool = field(metadata=_doc("Byte4 bit3"))
    chg_mos_adhesion_err: bool = field(metadata=_doc("Byte4 bit4"))
    dischg_mos_adhesion_err: bool = field(metadata=_doc("Byte4 bit5"))
    chg_mos_open_circuit_err: bool = field(metadata=_doc("Byte4 bit6"))
    discrg_mos_open_circuit_err: bool = field(metadata=_doc("Byte4 bit7"))

    # Byte5
    afe_collect_chip_err: bool = field(metadata=_doc("Byte5 bit0"))
    voltage_collect_dropped: bool = field(metadata=_doc("Byte5 bit1"))
    cell_temp_sensor_err: bool = field(metadata=_doc("Byte5 bit2"))
    eeprom_err: bool = field(metadata=_doc("Byte5 bit3"))
    rtc_err: bool = field(metadata=_doc("Byte5 bit4"))
    precharge_failure: bool = field(metadata=_doc("Byte5 bit5"))
    communication_failure: bool = field(metadata=_doc("Byte5 bit6"))
    internal_communication_failure: bool = field(metadata=_doc("Byte5 bit7"))

    # Byte6
    current_module_fault: bool = field(metadata=_doc("Byte6 bit0"))
    sum_voltage_detect_fault: bool = field(metadata=_doc("Byte6 bit1"))
    short_circuit_protect_fault: bool = field(metadata=_doc("Byte6 bit2"))
    low_volt_forbidden_chg_fault: bool = field(metadata=_doc("Byte6 bit3"))

    # Byte7
    fault_code: int = field(metadata=_doc("Byte7 fault code (0..255)"))

    @classmethod
    def from_frame(cls, frame: DalyBMSResponseFrame) -> "BatteryFailureStatusAnswer":
        b0 = int(frame.data[0])
        b1 = int(frame.data[1])
        b2 = int(frame.data[2])
        b3 = int(frame.data[3])
        b4 = int(frame.data[4])
        b5 = int(frame.data[5])
        b6 = int(frame.data[6])
        b7 = int(frame.data[7])

        def bit(v: int, n: int) -> bool:
            return bool((v >> n) & 0x01)

        return BatteryFailureStatusAnswer(
            # Byte0
            cell_volt_high_level_1=bit(b0, 0),
            cell_volt_high_level_2=bit(b0, 1),
            cell_volt_low_level_1=bit(b0, 2),
            cell_volt_low_level_2=bit(b0, 3),
            sum_volt_high_level_1=bit(b0, 4),
            sum_volt_high_level_2=bit(b0, 5),
            sum_volt_low_level_1=bit(b0, 6),
            sum_volt_low_level_2=bit(b0, 7),
            # Byte1
            chg_temp_high_level_1=bit(b1, 0),
            chg_temp_high_level_2=bit(b1, 1),
            chg_temp_low_level_1=bit(b1, 2),
            chg_temp_low_level_2=bit(b1, 3),
            dischg_temp_high_level_1=bit(b1, 4),
            dischg_temp_high_level_2=bit(b1, 5),
            dischg_temp_low_level_1=bit(b1, 6),
            dischg_temp_low_level_2=bit(b1, 7),
            # Byte2
            chg_overcurrent_level_1=bit(b2, 0),
            chg_overcurrent_level_2=bit(b2, 1),
            dischg_overcurrent_level_1=bit(b2, 2),
            dischg_overcurrent_level_2=bit(b2, 3),
            soc_high_level_1=bit(b2, 4),
            soc_high_level_2=bit(b2, 5),
            soc_low_level_1=bit(b2, 6),
            soc_low_level_2=bit(b2, 7),
            # Byte3
            diff_volt_level_1=bit(b3, 0),
            diff_volt_level_2=bit(b3, 1),
            diff_temp_level_1=bit(b3, 2),
            diff_temp_level_2=bit(b3, 3),
            # Byte4
            chg_mos_temp_high_alarm=bit(b4, 0),
            dischg_mos_temp_high_alarm=bit(b4, 1),
            chg_mos_temp_sensor_err=bit(b4, 2),
            dischg_mos_temp_sensor_err=bit(b4, 3),
            chg_mos_adhesion_err=bit(b4, 4),
            dischg_mos_adhesion_err=bit(b4, 5),
            chg_mos_open_circuit_err=bit(b4, 6),
            discrg_mos_open_circuit_err=bit(b4, 7),
            # Byte5
            afe_collect_chip_err=bit(b5, 0),
            voltage_collect_dropped=bit(b5, 1),
            cell_temp_sensor_err=bit(b5, 2),
            eeprom_err=bit(b5, 3),
            rtc_err=bit(b5, 4),
            precharge_failure=bit(b5, 5),
            communication_failure=bit(b5, 6),
            internal_communication_failure=bit(b5, 7),
            # Byte6
            current_module_fault=bit(b6, 0),
            sum_voltage_detect_fault=bit(b6, 1),
            short_circuit_protect_fault=bit(b6, 2),
            low_volt_forbidden_chg_fault=bit(b6, 3),
            # Byte7
            fault_code=b7,
        )


@dataclass
class CellVoltagesAnswer:
    """
    Cell voltages 1~48 (Data ID 0x95), §3.

    The voltage of each monomer is 2 byte, according to the
    actual number of cell, the maximum 96 byte, is sent in
    16 frames
    Byte0:frame number, starting from 0,0xFF invalid
    Byte1~byte6:Cell voltage (1 mV)
    Byte7: Reserved
    """

    cells: list[float] = field(
        metadata=_doc("Cell voltages, in volts, ordered by cell number")
    )

    @classmethod
    def from_frames(
        cls, frames: list[DalyBMSResponseFrame], cell_count: int = 48
    ) -> "CellVoltagesAnswer":
        """
        Parse CellVoltagesAnswer from Daly BMS response frames.

        Args:
            frames: Daly BMS response frames.
            cell_count: The number of cells.

        Returns:
            CellVoltagesAnswer.

        Raises:
            ValueError
        """
        cells: list[float] = []

        # check max cell count
        if cell_count > 48:
            raise ValueError("cell_count must be <= 48")
        # check min cell count
        if cell_count < 1:
            raise ValueError("cell_count must be >= 1")
        # check frames count
        if len(frames) > 16:
            raise ValueError("frames must be <= 16")
        if len(frames) < 1:
            raise ValueError("frames must be >= 1")

        for frame_no_expected, frame in enumerate(frames, start=1):
            # Check frame number
            frame_no = frame.data[0]
            if frame_no != frame_no_expected:
                raise ValueError(
                    f"Frame number mismatch: expected {frame_no_expected}, got {frame_no}"
                )

            # The voltage of each monomer is 2 byte
            # Byte1~byte6:Cell voltage (1 mV)
            for i in range(1, 6, 2):
                # Check if we have enough cells
                if len(cells) == cell_count:
                    break

                cell_voltage = struct.unpack(">H", frame.data[i : i + 2])[0]
                cells.append(cell_voltage / 1000.0)

        return CellVoltagesAnswer(cells=cells)
