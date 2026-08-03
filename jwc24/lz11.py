"""Nintendo LZ11 compression used by Wii channel executables."""

from __future__ import annotations

from collections import defaultdict, deque


def decode_lz11(payload: bytes) -> bytes:
    if len(payload) < 4 or payload[0] != 0x11:
        raise ValueError("payload is not Nintendo LZ11")
    expected = int.from_bytes(payload[1:4], "little")
    source = 4
    if expected == 0:
        if len(payload) < 8:
            raise ValueError("truncated extended LZ11 header")
        expected = int.from_bytes(payload[4:8], "little")
        source = 8
    output = bytearray()
    while len(output) < expected:
        if source >= len(payload):
            raise ValueError("truncated LZ11 flag group")
        flags = payload[source]
        source += 1
        for bit in range(7, -1, -1):
            if len(output) >= expected:
                break
            if not flags & (1 << bit):
                if source >= len(payload):
                    raise ValueError("truncated LZ11 literal")
                output.append(payload[source])
                source += 1
                continue
            first = payload[source]
            source += 1
            marker = first >> 4
            if marker == 0:
                second, third = payload[source : source + 2]
                source += 2
                length = ((first & 0xF) << 4 | second >> 4) + 0x11
                distance = ((second & 0xF) << 8 | third) + 1
            elif marker == 1:
                second, third, fourth = payload[source : source + 3]
                source += 3
                length = (
                    (first & 0xF) << 12 | second << 4 | third >> 4
                ) + 0x111
                distance = ((third & 0xF) << 8 | fourth) + 1
            else:
                second = payload[source]
                source += 1
                length = marker + 1
                distance = ((first & 0xF) << 8 | second) + 1
            if distance > len(output):
                raise ValueError("invalid LZ11 back-reference")
            for _ in range(length):
                output.append(output[-distance])
                if len(output) == expected:
                    break
    return bytes(output)


def encode_lz11(payload: bytes) -> bytes:
    if not payload or len(payload) >= 1 << 24:
        raise ValueError("payload size must fit the standard LZ11 header")
    output = bytearray(b"\x11" + len(payload).to_bytes(3, "little"))
    positions: dict[bytes, deque[int]] = defaultdict(deque)
    cursor = 0

    def remember(position: int) -> None:
        if position + 3 > len(payload):
            return
        bucket = positions[payload[position : position + 3]]
        bucket.append(position)
        while bucket and position - bucket[0] > 4096:
            bucket.popleft()

    while cursor < len(payload):
        flag_offset = len(output)
        output.append(0)
        flags = 0
        for bit in range(8):
            if cursor >= len(payload):
                break
            best_length = best_distance = 0
            maximum = min(272, len(payload) - cursor)
            for candidate in reversed(positions.get(payload[cursor : cursor + 3], ())):
                distance = cursor - candidate
                if distance > 4096:
                    break
                length = 3
                while length < maximum and payload[candidate + length] == payload[cursor + length]:
                    length += 1
                if length > best_length:
                    best_length, best_distance = length, distance
                    if length == maximum:
                        break
            if best_length >= 3:
                flags |= 1 << (7 - bit)
                displacement = best_distance - 1
                if best_length <= 16:
                    output.extend((((best_length - 1) << 12) | displacement).to_bytes(2, "big"))
                else:
                    encoded_length = best_length - 0x11
                    output.extend(
                        bytes(
                            (
                                encoded_length >> 4,
                                (encoded_length & 0xF) << 4 | displacement >> 8,
                                displacement & 0xFF,
                            )
                        )
                    )
                start = cursor
                cursor += best_length
                for position in range(start, cursor):
                    remember(position)
            else:
                output.append(payload[cursor])
                remember(cursor)
                cursor += 1
        output[flag_offset] = flags
    return bytes(output)
