"""Bounded LZ10/LZ11 streaming inspection and original CMOC wrapper results.

Decoded bytes, SDK status, application count and retained state are distinct.
This module does not create missing input, resource envelopes or authentication.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompressionStep:
    return_value: int
    sdk_return: int | None
    remaining: int
    cached_remaining: int
    header_remaining: int
    variant: int
    reference_state: int
    reference_word: int
    flag_byte: int
    flag_bits_remaining: int
    output_size: int
    written: bytes = field(repr=False)


@dataclass(frozen=True)
class CompressionInspection:
    application: bool
    enabled: bool
    output_limit: int
    steps: tuple[CompressionStep, ...]
    output: bytes = field(repr=False)

    def metadata(self):
        return dict(application=self.application, enabled=self.enabled,
                    output_limit=self.output_limit, output_size=len(self.output),
                    steps=[dict(return_value=s.return_value, sdk_return=s.sdk_return,
                                remaining=s.remaining, cached_remaining=s.cached_remaining,
                                header_remaining=s.header_remaining, variant=s.variant,
                                reference_state=s.reference_state,
                                reference_word=s.reference_word, flag_byte=s.flag_byte,
                                flag_bits_remaining=s.flag_bits_remaining,
                                output_size=s.output_size, written_size=len(s.written)) for s in self.steps],
                    resource_envelope_verified=False, service_authentication_established=False)


class _Stream:
    def __init__(self, enabled, limit, capacity):
        self.enabled, self.limit, self.capacity = enabled, limit, capacity
        self.output = bytearray()
        self.remaining = self.cached = self.word = self.flags = self.bits = self.variant = 0
        self.header = 8 if enabled else 0
        self.reference = 3 if enabled else 0

    def byte(self, value):
        if len(self.output) >= self.capacity:
            raise ValueError('CMOC decompressor write exceeds explicit output backing')
        self.output.append(value)

    def sdk(self, chunk):
        pos = 0
        if self.header:
            if self.header == 8:
                if not chunk:
                    raise ValueError('CMOC initial decoder lacks its first supplied byte')
                kind = chunk[0]
                if kind >> 4 != 1:
                    return -1
                self.variant = kind & 15
                if self.variant not in (0, 1):
                    return -1
            while self.header and pos < len(chunk):
                self.header -= 1
                value = chunk[pos]
                pos += 1
                if self.header <= 3:
                    self.remaining |= value << ((3 - self.header) * 8)
                elif self.header <= 6:
                    self.remaining |= value << ((6 - self.header) * 8)
                if self.header == 4 and self.remaining > 0:
                    self.header = 0
            if not self.header:
                if self.remaining > 4096:
                    raise ValueError('CMOC declared output exceeds local inspection bound')
                if 0 < self.limit < self.remaining:
                    self.remaining = self.limit
            if pos == len(chunk):
                return -1 if self.header else self.remaining
        while self.remaining > 0:
            if self.bits == 0:
                if pos == len(chunk):
                    return self.remaining
                self.flags, self.bits = chunk[pos], 8
                pos += 1
            if pos == len(chunk):
                return self.remaining
            if not self.flags & 128:
                self.byte(chunk[pos])
                pos += 1
                self.remaining -= 1
            else:
                while self.reference:
                    self.reference -= 1
                    value = chunk[pos]
                    pos += 1
                    if self.variant == 0:
                        self.word, self.reference = value + 0x30, 0
                    elif self.reference == 2:
                        top = value >> 4
                        if top == 1:
                            self.word = ((value & 15) << 16) + 0x1110
                        elif top == 0:
                            self.word, self.reference = ((value & 15) << 8) + 0x110, 1
                        else:
                            self.word, self.reference = value + 0x10, 0
                    elif self.reference == 1:
                        self.word += value << 8
                    else:
                        self.word += value
                    if pos == len(chunk):
                        return self.remaining
                distance = ((self.word & 15) << 8 | chunk[pos]) + 1
                length = self.word >> 4
                pos += 1
                self.word, self.reference = length, 3
                if length > self.remaining:
                    if not self.limit:
                        return -4
                    length = self.word = self.remaining
                if distance > len(self.output):
                    raise ValueError('CMOC backreference precedes explicit output history')
                for _ in range(length):
                    self.byte(self.output[-distance])
                    self.remaining -= 1
                    self.word -= 1
            if self.remaining == 0:
                break
            self.flags = (self.flags << 1) & 255
            self.bits -= 1
        return -3 if not self.limit and len(chunk) - pos > 32 else 0


def _validate_inputs(chunks, enabled, output_limit, output_capacity, application):
    if (type(chunks) is not tuple or len(chunks) > 64
            or any(type(c) is not bytes for c in chunks) or sum(map(len, chunks)) > 4096
            or type(enabled) is not bool or type(application) is not bool
            or type(output_limit) is not int or not 0 <= output_limit <= 4096
            or type(output_capacity) is not int or not 1 <= output_capacity <= 4096
            or not application and not enabled):
        raise ValueError('Expected bounded explicit CMOC compression inputs')


def inspect_compression(*, chunks, enabled, output_limit, output_capacity,
                        application=True):
    """Replay supplied chunks without conflating SDK and application success.

    Application first-header reads require four or eight actual backing bytes.
    Direct SDK mode can retain partial header/token state across calls. Output
    limits are original decoder limits, not substitutes for allocated backing.
    """
    _validate_inputs(chunks, enabled, output_limit, output_capacity, application)
    stream = _Stream(enabled, output_limit, output_capacity)
    rows = []
    for chunk in chunks:
        previous = len(stream.output)
        sdk = None
        if not enabled:
            for value in chunk:
                stream.byte(value)
            result = len(chunk)
        elif application and stream.remaining <= 0 and stream.header == 0:
            result = 0
        else:
            if application and stream.cached == 0:
                if len(chunk) < 4:
                    raise ValueError('CMOC application lacks complete declared-size header backing')
                declared = int.from_bytes(chunk[1:4], 'little')
                if declared == 0:
                    if len(chunk) < 8:
                        raise ValueError('CMOC application lacks extended-size header backing')
                    declared = int.from_bytes(chunk[4:8], 'little')
                if declared > 4096:
                    raise ValueError('CMOC declared output exceeds local inspection bound')
                stream.cached = declared
            sdk = stream.sdk(chunk)
            if application:
                result = 0 if sdk < 0 else (stream.cached - sdk) & 0xFFFFFFFF
                if sdk >= 0:
                    stream.cached = sdk
            else:
                result = sdk
        rows.append(CompressionStep(result, sdk, stream.remaining, stream.cached,
            stream.header, stream.variant, stream.reference, stream.word, stream.flags, stream.bits,
            len(stream.output), bytes(stream.output[previous:])))
    return CompressionInspection(application, enabled, output_limit, tuple(rows), bytes(stream.output))
