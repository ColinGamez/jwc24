"""Bounded CMOC callback state projection with explicit transform boundaries.

No supplied transform or digest result authenticates service data. Input spans
represent captured backing storage; bytes missing from it are never invented.
"""
from dataclasses import dataclass, field


def _span(value, limit):
    if type(value) is not bytes or len(value) > limit:
        raise ValueError('Expected bounded explicit CMOC callback bytes')
    return value


def _integer(value, limit):
    if type(value) is not int or not 0 <= value <= limit:
        raise ValueError('Expected bounded explicit CMOC callback integer')
    return value


@dataclass(frozen=True)
class CallbackState:
    response_flags: int
    expected_wire_prefix: bytes = field(repr=False)
    expected_cached_prefix: bytes = field(repr=False)
    decoded_body: bytes = field(repr=False)
    hash_span_size: int
    hash_enabled: bool

    def __post_init__(self):
        _integer(self.response_flags, 255)
        _span(self.expected_wire_prefix, 64)
        _span(self.expected_cached_prefix, 64)
        _span(self.decoded_body, 4096)
        _integer(self.hash_span_size, 64)
        if type(self.hash_enabled) is not bool:
            raise ValueError('Expected explicit CMOC callback hash predicate')


@dataclass(frozen=True)
class CallbackStep:
    state: CallbackState = field(repr=False)
    kind: str
    wire_prefix_compared: bool
    cached_prefix_compared: bool
    padded_transform_size: int
    digest_boundary_consulted: bool
    forced_cached_comparison_at_finish: bool

    def metadata(self):
        return dict(kind=self.kind, response_flags=self.state.response_flags,
                    decoded_size=len(self.state.decoded_body),
                    wire_prefix_compared=self.wire_prefix_compared,
                    cached_prefix_compared=self.cached_prefix_compared,
                    padded_transform_size=self.padded_transform_size,
                    digest_boundary_consulted=self.digest_boundary_consulted,
                    forced_cached_comparison_at_finish=self.forced_cached_comparison_at_finish,
                    configured_transforms_verified=False,
                    service_authentication_verified=False)


def _next(state, flags, body):
    return CallbackState(flags, state.expected_wire_prefix, state.expected_cached_prefix,
                         body, state.hash_span_size, state.hash_enabled)


def process_body_event(state, *, wire_storage, receive_end_offset,
                       decoded_chunk, raw_body):
    """Project event 2 using an explicit backing snapshot and transform output.

    The native raw branch sets total decoded size directly. Configured inputs
    supply the decompressor's output explicitly; no hash, cipher or compression
    algorithm is inferred here. Local size limits are deliberately bounded.
    """
    if type(state) is not CallbackState:
        raise ValueError('Expected explicit CMOC callback state')
    _span(wire_storage, 0x440)
    _integer(receive_end_offset, 0x30000)
    flags = state.response_flags
    padded = 0
    if flags & 0x80:
        _span(raw_body, 4096)
        if decoded_chunk is not None or receive_end_offset != len(raw_body):
            raise ValueError('Raw CMOC callback requires its total body snapshot')
        body = raw_body
    else:
        _span(decoded_chunk, 1024)
        if raw_body is not None:
            raise ValueError('Configured CMOC callback cannot imply raw transport')
        source_offset = state.hash_span_size + len(state.expected_wire_prefix)
        if receive_end_offset < source_offset:
            raise ValueError('CMOC callback receive extent precedes transform input')
        padded = (receive_end_offset - source_offset + 15) & ~15
        if padded > 1024 or source_offset + padded > len(wire_storage):
            raise ValueError('CMOC callback lacks explicit padded backing bytes')
        body = state.decoded_body + decoded_chunk
        _span(body, 4096)
    wire_compared = False
    if not flags & 0x08:
        prefix = state.expected_wire_prefix
        if len(wire_storage) < len(prefix):
            raise ValueError('CMOC callback lacks explicit wire comparison bytes')
        if prefix:
            wire_compared = True
            if wire_storage[:len(prefix)] != prefix:
                flags |= 0x40
        flags |= 0x08
    cached_compared = False
    if not flags & 0x04 and len(body) >= len(state.expected_cached_prefix):
        prefix = state.expected_cached_prefix
        if prefix:
            cached_compared = True
            if body[:len(prefix)] != prefix:
                flags |= 0x20
        flags |= 0x04
    return CallbackStep(_next(state, flags, body), 'body', wire_compared,
                        cached_compared, padded, False, False)


def finish_callback(state, *, digest_matches):
    """Project event 4; an incomplete cached-prefix check forces bits 20/04."""
    if type(state) is not CallbackState:
        raise ValueError('Expected explicit CMOC callback state')
    consult = not state.response_flags & 0x80 and state.hash_enabled
    if (consult and type(digest_matches) is not bool) or (not consult and digest_matches is not None):
        raise ValueError('CMOC digest boundary result must match the explicit branch')
    flags = state.response_flags
    forced = not flags & 0x04
    if forced:
        flags |= 0x24
    if consult and not digest_matches:
        flags |= 0x10
    flags |= 0x02
    return CallbackStep(_next(state, flags, state.decoded_body), 'finish', False,
                        False, 0, consult, forced)
