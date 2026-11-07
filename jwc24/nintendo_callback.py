"""Original HATJ SDK event-four producer and supplied manager/HTTP handoff.

SDK getter values and ticks remain caller assertions. A retained response word
of 200 is not an observation that an HTTP response was received or accepted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import struct

from .nintendo_http import NintendoHTTPState, _state as _http_state, _u32, _signed
from .nintendo_load import NintendoLoadError
from .nintendo_manager import NintendoManagerState, NintendoManagerDelivery, apply_manager_callback
from .nintendo_request import NintendoRequestState, NintendoRequestCall, INNER, _state as _request_state, TICK

CONTEXT, ERROR, DETAIL, PHASE, RESPONSE = 0x802A9EA0, 0x802A9F20, 0x802A9F70, 0x802A9E50, 0x802AA5A0
_GETTERS = frozenset((CONTEXT, ERROR, DETAIL, PHASE, RESPONSE))


@dataclass(frozen=True)
class NintendoSDKEventInputs:
    event_word: int = field(repr=False)
    sdk_handle_word: int = field(repr=False)
    descriptor: bytes = field(repr=False)
    frequency_word: int = field(repr=False)


@dataclass(frozen=True)
class NintendoSDKEventResult:
    request: NintendoRequestState = field(repr=False)
    loader: NintendoHTTPState = field(repr=False)
    calls: tuple[NintendoRequestCall, ...] = field(repr=False)
    delivery: NintendoManagerDelivery | None = field(repr=False)
    inner_callback_invoked: bool
    manager_relay_invoked: bool
    detail_getter_called: bool
    response_getter_called: bool

    def metadata(self):
        return {'event_word_four_projected': True, 'wrapper_return_word_zero': True,
                'inner_callback_invoked': self.inner_callback_invoked,
                'manager_relay_invoked': self.manager_relay_invoked,
                'http_callback_consumed': self.delivery is not None and self.delivery.callback is not None,
                'detail_getter_called': self.detail_getter_called,
                'response_getter_called': self.response_getter_called,
                'prior_response_word_retained': not self.response_getter_called,
                'sdk_boundary_calls': sum(x.address != TICK for x in self.calls),
                'tick_boundary_calls': sum(x.address == TICK for x in self.calls),
                'sdk_observations_are_caller_assertions': True,
                'actual_http_response_or_authentication_verified': False,
                'async_lifetime_or_catalog_completion_verified': False,
                'native_payload_or_request_published': False}


def _inputs(value):
    if type(value) is not NintendoSDKEventInputs:
        raise NintendoLoadError('Expected explicit SDK callback inputs')
    for name in ('event_word', 'sdk_handle_word', 'frequency_word'):
        _u32(getattr(value, name))
    if value.event_word != 4:
        raise NintendoLoadError('Only the reviewed event-four producer is implemented')
    if type(value.descriptor) is not bytes or len(value.descriptor) > 256:
        raise NintendoLoadError('SDK descriptor exceeds the bounded event-four subset')
    if value.frequency_word < 4:
        raise NintendoLoadError('Supplied frequency would make the reviewed division undefined')
    return value


def apply_sdk_event4(request: NintendoRequestState, loader: NintendoHTTPState,
                     inputs: NintendoSDKEventInputs, *, loader_context_word: int,
                     sdk_results: tuple[tuple[int, int], ...],
                     tick_words: tuple[tuple[int, int], ...]) -> NintendoSDKEventResult:
    """Project the complete event-four path through its configured native chain.

    Getter returns do not mutate application RAM or invoke further callbacks in
    this bounded slice. The descriptor is retained; event four does not use it.
    A foreign nonzero context/callback cannot be redirected to the given state.
    """
    request, loader, inputs = _request_state(request), _http_state(loader), _inputs(inputs)
    _u32(loader_context_word)
    if not loader_context_word or request.retry_word != loader.retry_word:
        raise NintendoLoadError('Supplied loader identity or shared retry snapshots disagree')
    if (type(sdk_results) is not tuple or len(sdk_results) > 5
            or type(tick_words) is not tuple or len(tick_words) > 1):
        raise NintendoLoadError('Expected bounded explicit getter and tick sequences')
    for pair in sdk_results:
        if type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not int or pair[0] not in _GETTERS:
            raise NintendoLoadError('Unsupported SDK getter outcome')
        _u32(pair[1])
    for pair in tick_words:
        if type(pair) is not tuple or len(pair) != 2:
            raise NintendoLoadError('Expected explicit two-word ticks')
        for value in pair:
            _u32(value)
    remaining, ticks, calls = list(sdk_results), list(tick_words), []
    raw = bytearray(request.storage)

    def word(offset):
        return struct.unpack_from('>I', raw, offset)[0]

    def store(offset, value):
        struct.pack_into('>I', raw, offset, value & 0xFFFFFFFF)

    def getter(address, handle):
        if not remaining or remaining[0][0] != address:
            raise NintendoLoadError('Getter outcome sequence does not match the observed branch')
        _, result = remaining.pop(0)
        calls.append(NintendoRequestCall(address, (handle,), (result,)))
        return result

    if getter(CONTEXT, inputs.sdk_handle_word) != request.object_word + INNER:
        raise NintendoLoadError('SDK callback context does not identify the supplied inner object')
    shared = request.shared_word
    if shared == 2:
        shared = 3
        if not ticks:
            raise NintendoLoadError('Missing explicit event-four tick observation')
        pair = ticks.pop(0)
        calls.append(NintendoRequestCall(TICK, (), pair))
        now = pair[0] << 32 | pair[1]
        before = word(INNER + 0xF8) << 32 | word(INNER + 0xFC)
        delta = (now - before) & 0xFFFFFFFFFFFFFFFF
        signed_delta = delta - 0x10000000000000000 if delta & 0x8000000000000000 else delta
        # The original 64-bit helper performs signed division toward zero.
        elapsed = abs(signed_delta) // (inputs.frequency_word >> 2)
        if signed_delta < 0:
            elapsed = -elapsed
        low = elapsed & 0xFFFFFFFF
        store(INNER + 0x100, word(INNER + 0x10) // low if low else 0)
    elif shared == 4:
        shared = 5
    for offset in (0x18, 0x58, 0x78, 0xB8):
        raw[INNER + offset] = 0
    handle = word(INNER)
    error = getter(ERROR, handle)
    store(INNER + 0x118, error)
    detail_called = error == 14
    if detail_called:
        store(INNER + 0x11C, getter(DETAIL, handle))
    response_called = _signed(getter(PHASE, handle)) >= 4
    if response_called:
        store(INNER + 0x120, getter(RESPONSE, handle))
    if remaining or ticks:
        raise NintendoLoadError('Unused supplied getter or tick observations')
    inner_callback = word(INNER + 8)
    invoked = inner_callback != 0
    relay = False
    delivery = None
    if invoked:
        if inner_callback != 0x80026AE0:
            raise NintendoLoadError('Inner callback is outside the reviewed native relay chain')
        context = word(INNER + 12)
        if context:
            if context != request.object_word:
                raise NintendoLoadError('Inner callback context identifies another manager')
            outer_callback = word(0x29AC)
            if outer_callback not in (0, 0x800287C0):
                raise NintendoLoadError('Outer callback is outside the reviewed native loader chain')
            relay = True
            snapshot = NintendoManagerState(True, outer_callback != 0, word(0x29B0), shared,
                                            word(INNER + 0x10), error, word(INNER + 0x11C),
                                            word(INNER + 0x120), word(INNER + 0x128))
            delivery = apply_manager_callback(loader, snapshot, b'', loader_context_word=loader_context_word)
            loader = delivery.state
    updated = NintendoRequestState(request.object_word, bytes(raw), shared, loader.retry_word)
    return NintendoSDKEventResult(updated, loader, tuple(calls), delivery, invoked, relay,
                                   detail_called, response_called)
