"""
Daly BMS frames per the "UART/485 Communications Protocol" datasheet.
§2.3.1 — host request, §2.3.2 — slave (BMS) response.

Second layer OSI, Frame, §2.3.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum

RESPONSE_FRAME_LEN = 13
RESPONSE_DATA_LEN = 8
RESPONSE_START_FLAG = 0xA5
# In the slave (BMS) response, the second byte is 0x01, §2.2 "BMS master 0x01".
RESPONSE_BMS_ADDRESS = 0x01
# Data-length field is fixed to 8 bytes (0x08 in the frame).
RESPONSE_DATA_LENGTH_FIELD = 0x08


class DalyBMSCommand(Enum):
    """
    Data ID, §3 "Communications content information" (names follow the datasheet).
    """

    SOC = 0x90
    VOLTAGE_MIN_MAX = 0x91
    TEMPERATURE_MIN_MAX = 0x92
    MOS = 0x93
    STATUS_1 = 0x94
    CELL_V = 0x95
    CELL_T = 0x96
    BALANCE = 0x97
    FAULT = 0x98


class DalyBMSHostAddress(IntEnum):
    """
    Host nibble: the 2nd byte of the *request* is (nibble & 0xF) << 4, §2.2 / §2.3.1.
    """

    GPRS = 2  # 0x20
    PC = 4  # 0x40, Upper computer
    BT = 8  # 0x80, Bluetooth


# --- Methods ---``


def daly_link_checksum_12b(data: bytes) -> int:
    """
    Calculate checksum for Daly BMS response frame, §2.3.2.

    Args:
        data: Data to calculate checksum for, first 12 bytes of the frame.

    Returns:
        Checksum for the data.

    Raises:
        ValueError: If the data is invalid.
    """
    if len(data) != RESPONSE_FRAME_LEN - 1:
        raise ValueError(
            f"expected {RESPONSE_FRAME_LEN - 1} wire bytes, got {len(data)}"
        )
    return sum(data) & 0xFF


# def build_daly_read_request_frame(host_nibble: int, data_id: int) -> bytes:
#     """
#     Read request: 0xA5, (nibble<<4), Data ID, 0x08, 8 zeros, + 1 byte checksum.
#     """
#     if not (0 <= host_nibble <= 15):
#         raise ValueError("host nibble 0..15")
#     body = bytearray(REQUEST_HEADER_LEN)
#     body[0] = RESPONSE_START_FLAG
#     body[1] = (host_nibble & 0x0F) << 4
#     body[2] = data_id
#     body[3] = RESPONSE_DATA_LENGTH_FIELD
#     b = bytes(body)
#     return b + bytes([daly_link_checksum_12b(b)])


@dataclass(frozen=True)
class DalyBMSResponseFrame:
    """
    Raw response frame from Daly BMS
    """

    bms_address: int
    data_id: int
    data_length: int
    data: bytes

    def __post_init__(self) -> None:
        if len(self.data) != RESPONSE_DATA_LEN:
            raise ValueError("data must be 8 bytes")

    @classmethod
    def from_bytes(cls, raw: bytes) -> DalyBMSResponseFrame:
        """
        Parse raw response frame from Daly BMS, §2.3.2.

        Args:
            raw: Raw response frame from Daly BMS, §2.3.2.

        Returns:
            DalyBMSResponseFrame: Parsed response frame.

        Raises:
            ValueError: If the raw frame is invalid
        """
        if len(raw) != RESPONSE_FRAME_LEN:
            raise ValueError(
                f"expected {RESPONSE_FRAME_LEN} wire bytes, got {len(raw)}"
            )
        if raw[0] != RESPONSE_START_FLAG:
            raise ValueError("start must be 0xA5")
        # if daly_link_checksum_12b(raw[:12]) != raw[12]:
        #     raise ValueError("checksum mismatch")
        if raw[1] != RESPONSE_BMS_ADDRESS:
            raise ValueError(
                f"BMS/slave address 0x{raw[1]:02x}, expected 0x{RESPONSE_BMS_ADDRESS:02x} (§2.2)"
            )
        if raw[3] != RESPONSE_DATA_LENGTH_FIELD:
            raise ValueError("data length field must be 8 (0x08)")
        # if expect_data_id is not None and raw[2] != expect_data_id:
        #     raise ValueError(
        #         f"Data ID 0x{raw[2]:02x}, expected 0x{expect_data_id:02x}"
        #     )
        return cls(
            bms_address=raw[1],
            data_id=raw[2],
            data_length=raw[3],
            data=bytes(raw[4:12]),
        )
