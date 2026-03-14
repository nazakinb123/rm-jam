from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Dict, List, Optional


SOF = 0xA5
CMD_ID_KEY = 0x0A06
KEY_PATTERN = re.compile(r"^[A-Z0-9]{6}$")


def _generate_crc8_table() -> List[int]:
    # RM docs table matches reflected CRC8 polynomial 0x8C.
    table: List[int] = []
    for i in range(256):
        c = i
        for _ in range(8):
            if c & 0x01:
                c = ((c >> 1) ^ 0x8C) & 0xFF
            else:
                c = (c >> 1) & 0xFF
        table.append(c)
    return table


def _generate_crc16_table() -> List[int]:
    # RM docs table matches reflected CRC16 polynomial 0x8408.
    table: List[int] = []
    for i in range(256):
        c = i
        for _ in range(8):
            if c & 0x01:
                c = (c >> 1) ^ 0x8408
            else:
                c >>= 1
        table.append(c & 0xFFFF)
    return table


CRC8_INIT = 0xFF
CRC16_INIT = 0xFFFF
CRC8_TABLE = _generate_crc8_table()
CRC16_TABLE = _generate_crc16_table()


@dataclass
class ParseStats:
    parsed_frames: int = 0
    valid_frames: int = 0
    crc_fail_frames: int = 0
    ascii_fail_frames: int = 0
    non_target_frames: int = 0
    length_fail_frames: int = 0


@dataclass
class ParseResult:
    keys: List[str]
    key_counts: Dict[str, int]
    best_key: Optional[str]
    best_key_count: int
    stats: ParseStats


def crc8(data: bytes, init: int = CRC8_INIT) -> int:
    c = init & 0xFF
    for b in data:
        c = CRC8_TABLE[(c ^ b) & 0xFF]
    return c


def crc16(data: bytes, init: int = CRC16_INIT) -> int:
    c = init & 0xFFFF
    for b in data:
        c = ((c >> 8) ^ CRC16_TABLE[(c ^ b) & 0xFF]) & 0xFFFF
    return c


def verify_crc8_header(header_5b: bytes) -> bool:
    if len(header_5b) != 5:
        return False
    return crc8(header_5b[:4]) == header_5b[4]


def verify_crc16_frame(frame: bytes) -> bool:
    if len(frame) < 9:
        return False
    expected = crc16(frame[:-2])
    got = int.from_bytes(frame[-2:], byteorder="little", signed=False)
    return expected == got


def build_frame(cmd_id: int, data: bytes, seq: int = 0) -> bytes:
    if not (0 <= cmd_id <= 0xFFFF):
        raise ValueError("cmd_id must be uint16")
    if not (0 <= seq <= 0xFF):
        raise ValueError("seq must be uint8")
    if len(data) > 0xFFFF:
        raise ValueError("data too long for protocol frame")

    header = bytearray()
    header.append(SOF)
    header.extend(len(data).to_bytes(2, byteorder="little", signed=False))
    header.append(seq)
    header.append(0)
    header[4] = crc8(bytes(header[:4]))

    frame_wo_crc16 = bytes(header) + cmd_id.to_bytes(2, byteorder="little", signed=False) + data
    tail = crc16(frame_wo_crc16).to_bytes(2, byteorder="little", signed=False)
    return frame_wo_crc16 + tail


def parse_stream(raw_bytes: bytes, max_data_len: int = 2048) -> ParseResult:
    data = memoryview(raw_bytes)
    i = 0
    n = len(data)
    keys: List[str] = []
    stats = ParseStats()

    while i + 5 <= n:
        if data[i] != SOF:
            i += 1
            continue

        header = bytes(data[i : i + 5])
        if not verify_crc8_header(header):
            stats.crc_fail_frames += 1
            i += 1
            continue

        data_len = int.from_bytes(data[i + 1 : i + 3], byteorder="little", signed=False)
        if data_len > max_data_len:
            i += 1
            continue

        frame_len = 5 + 2 + data_len + 2
        if i + frame_len > n:
            break

        frame = bytes(data[i : i + frame_len])
        if not verify_crc16_frame(frame):
            stats.crc_fail_frames += 1
            i += 1
            continue

        stats.parsed_frames += 1
        cmd_id = int.from_bytes(frame[5:7], byteorder="little", signed=False)
        payload = frame[7 : 7 + data_len]

        if cmd_id != CMD_ID_KEY:
            stats.non_target_frames += 1
            i += frame_len
            continue

        if data_len != 6:
            stats.length_fail_frames += 1
            i += frame_len
            continue

        try:
            key = payload.decode("ascii")
        except UnicodeDecodeError:
            stats.ascii_fail_frames += 1
            i += frame_len
            continue

        if not KEY_PATTERN.fullmatch(key):
            stats.ascii_fail_frames += 1
            i += frame_len
            continue

        keys.append(key)
        stats.valid_frames += 1
        i += frame_len

    counts = Counter(keys)
    if counts:
        best_key, best_count = counts.most_common(1)[0]
    else:
        best_key, best_count = None, 0

    return ParseResult(
        keys=keys,
        key_counts=dict(counts),
        best_key=best_key,
        best_key_count=best_count,
        stats=stats,
    )


def _self_test() -> None:
    assert CRC8_TABLE[:8] == [0x00, 0x5E, 0xBC, 0xE2, 0x61, 0x3F, 0xDD, 0x83]
    assert CRC16_TABLE[:8] == [0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD, 0x6536, 0x74BF]

    good = build_frame(CMD_ID_KEY, b"A1B2C3", seq=7)
    pr_good = parse_stream(good)
    assert pr_good.stats.valid_frames == 1
    assert pr_good.best_key == "A1B2C3"

    bad_crc = bytearray(good)
    bad_crc[-1] ^= 0xAA
    noisy = b"\x13\x37\x00" + bytes(bad_crc) + good
    pr_noisy = parse_stream(noisy)
    assert pr_noisy.stats.valid_frames == 1
    assert pr_noisy.stats.crc_fail_frames >= 1

    wrong_ascii = build_frame(CMD_ID_KEY, b"A1b$%2", seq=9)
    pr_ascii = parse_stream(wrong_ascii)
    assert pr_ascii.stats.valid_frames == 0
    assert pr_ascii.stats.ascii_fail_frames == 1


if __name__ == "__main__":
    _self_test()
    print("protocol_rm self-test passed.")
