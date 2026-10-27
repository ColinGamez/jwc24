"""Explicit HATJ callback/poll state, without transport or authentication.

Native state words retain offset names. A skipped input chunk and a misleading
zero normalized result cannot become a complete catalog in the safe handoff.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from .nintendo_listdata import MAX_LIST_BYTES
from .nintendo_load import NintendoLoadError, inspect_japanese_list_download

_RETRY_DETAILS = frozenset((0x3FD22, 0x3FD23, 0x3FD24, 0x3FD28))
_TIMEOUT_DETAIL = 0x41E4C


def _u32(value):
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise NintendoLoadError('Expected an explicit native unsigned word')
    return value


def _i32(value):
    if type(value) is not int or not -0x80000000 <= value <= 0x7FFFFFFF:
        raise NintendoLoadError('Expected an explicit native signed result')
    return value


def _signed(value):
    return value - 0x100000000 if value & 0x80000000 else value


@dataclass(frozen=True)
class NintendoHTTPState:
    buffer: bytes = field(repr=False)
    copied_bytes: int = field(repr=False)
    word_04: int = field(repr=False)
    word_08: int = field(repr=False)
    word_0c: int = field(repr=False)
    error_word_1c: int = field(repr=False)
    error_word_20: int = field(repr=False)
    manager_error_word_2a70: int = field(repr=False)
    manager_error_word_2a74: int = field(repr=False)
    retry_word: int = field(repr=False)
    skipped_input: bool


def _state(value):
    if type(value) is not NintendoHTTPState:
        raise NintendoLoadError('Expected an explicit Nintendo HTTP state snapshot')
    if type(value.buffer) is not bytes or not 0 < len(value.buffer) <= MAX_LIST_BYTES:
        raise NintendoLoadError('Expected an explicit bounded native allocation buffer')
    if type(value.copied_bytes) is not int or not 0 <= value.copied_bytes <= len(value.buffer):
        raise NintendoLoadError('Retained byte count exceeds the supplied allocation')
    for name in ('word_04', 'word_08', 'word_0c', 'error_word_1c', 'error_word_20',
                 'manager_error_word_2a70', 'manager_error_word_2a74'):
        _u32(getattr(value, name))
    _i32(value.retry_word)
    if type(value.skipped_input) is not bool:
        raise NintendoLoadError('Expected explicit skipped-input history')
    return value


@dataclass(frozen=True)
class NintendoHTTPCallback:
    state: NintendoHTTPState = field(repr=False)
    received_bytes: int
    retained_bytes: int
    input_skipped: bool
    retry_scheduled: bool

    def metadata(self):
        return {'received_bytes': self.received_bytes, 'retained_bytes': self.retained_bytes,
                'input_skipped': self.input_skipped, 'retry_scheduled': self.retry_scheduled,
                'observed_callback_rules_applied': True,
                'network_callback_origin_verified': False,
                'authentication_or_catalog_completion_verified': False}


def apply_http_callback(state: NintendoHTTPState, chunk: bytes, *, word_08: int,
                        word_0c: int, word_10: int, word_14: int) -> NintendoHTTPCallback:
    """Project the actual chunk-copy and callback-state branches.

    All bytes/state are supplied explicitly. A dropped chunk does not create a
    native error here: the original callback can still enter its phase-three
    path. The separate safe handoff refuses that incomplete body.
    """
    state = _state(state)
    for value in (word_08, word_0c, word_10, word_14):
        _u32(value)
    if type(chunk) is not bytes or len(chunk) > MAX_LIST_BYTES:
        raise NintendoLoadError('Callback bytes exceed the bounded local subset')
    # The reviewed allocation and local chunk limits keep this sum below uint32
    # wrap. Corrupted native counters are outside this safer backend subset.
    fits = len(chunk) <= len(state.buffer) - state.copied_bytes
    skipped = bool(chunk) and not fits
    retained = len(chunk) if chunk and fits else 0
    updated = replace(state, skipped_input=state.skipped_input or skipped)
    if retained:
        end = state.copied_bytes + retained
        updated = replace(updated,
                          buffer=state.buffer[:state.copied_bytes] + chunk + state.buffer[end:],
                          copied_bytes=end, word_0c=word_0c)
    retry = False
    if word_08 != 2:
        if word_10 == 0:
            updated = replace(updated, word_0c=word_0c, word_08=3,
                              retry_word=0 if state.retry_word == -1 else state.retry_word)
        elif word_14 in _RETRY_DETAILS and state.retry_word == -1:
            updated = replace(updated, retry_word=1, word_04=2, word_08=7)
            retry = True
        else:
            updated = replace(updated, error_word_1c=word_10, error_word_20=word_14, word_08=6)
    return NintendoHTTPCallback(updated, len(chunk), retained, skipped, retry)


@dataclass(frozen=True)
class NintendoHTTPPoll:
    state: NintendoHTTPState = field(repr=False)
    raw_poll_result: int = field(repr=False)
    manager_result: int = field(repr=False)
    manager_27140_called: bool
    manager_271d0_called: bool
    restart_called: bool
    request_26c80_called: bool
    native_data_phase_reached: bool

    def metadata(self):
        return {'raw_poll_result_zero': self.raw_poll_result == 0,
                'manager_result_zero': self.manager_result == 0,
                'manager_27140_called': self.manager_27140_called,
                'manager_271d0_called': self.manager_271d0_called,
                'restart_called': self.restart_called,
                'request_26c80_called': self.request_26c80_called,
                'native_data_phase_reached': self.native_data_phase_reached,
                'input_skipped': self.state.skipped_input,
                'retained_bytes': self.state.copied_bytes,
                'timer_or_underlying_manager_results_independently_verified': False,
                'network_authentication_or_catalog_completion_verified': False}


def poll_http_state(state: NintendoHTTPState, *, timer_expired: bool,
                    manager_27140_result: int, request_manager_available: bool,
                    request_26c80_result: int, request_26c80_error_word: int) -> NintendoHTTPPoll:
    """Project real virtual poll/start branches and manager result normalization.

    The timer and underlying manager outcomes are explicit boundary inputs, not generated IO.
    A recognized negative result is normalized by returning the stored loader
    error word; that can be zero or positive. Both results remain distinct.
    """
    state = _state(state)
    if type(timer_expired) is not bool or type(request_manager_available) is not bool:
        raise NintendoLoadError('Expected explicit timer and request-manager predicates')
    _i32(manager_27140_result)
    _i32(request_26c80_result)
    _u32(request_26c80_error_word)
    updated = state
    wait = finalize = restart = request = False
    raw = -300
    if state.word_04 in (2, 3):
        if timer_expired:
            updated = replace(state, error_word_1c=(-109 & 0xFFFFFFFF),
                              error_word_20=_TIMEOUT_DETAIL)
            raw = -109
        elif state.word_08 == 2:
            raw = 1
        elif state.word_08 == 4:
            wait = True
            if manager_27140_result == 0:
                updated = replace(state, word_08=5)
                raw = 0
            else:
                raw = 1
        elif state.word_08 == 3:
            finalize = True
            raw = 0
        elif state.word_08 == 5:
            raw = 0
        elif state.word_08 == 6:
            raw = -109
        elif state.word_08 == 7:
            restart = True
            updated = replace(state, word_04=1)
            if request_manager_available:
                request = True
                # Original start resets the received-byte counter and word0c
                # before invoking its underlying request boundary. Old buffer
                # bytes remain, but are outside this new attempt's count.
                updated = replace(updated, copied_bytes=0, word_0c=0, skipped_input=False)
                if request_26c80_result < 0:
                    updated = replace(updated, error_word_1c=(-109 & 0xFFFFFFFF),
                                      error_word_20=request_26c80_error_word)
                    raw = -109
                else:
                    updated = replace(updated, word_04=2, word_08=2)
                    raw = 1
    # All projected raw results are in the actual normalizer's accepted set.
    if raw < 0:
        updated = replace(updated, manager_error_word_2a70=updated.error_word_1c,
                          manager_error_word_2a74=updated.error_word_20)
        result = _signed(updated.error_word_1c)
    else:
        result = raw
    data_phase = (updated.word_04 in (2, 3) and updated.word_08 in (3, 5)
                  and raw == result == 0)
    return NintendoHTTPPoll(updated, raw, result, wait, finalize, restart, request, data_phase)


def inspect_http_list_download(csdata_payload: bytes, poll: NintendoHTTPPoll, *,
                               service_prefix: bytes, language_code: int):
    """Use only retained body bytes after the observed native data phase.

    This is a deliberately stricter backend handoff. It verifies neither that
    callbacks originated from the planned endpoint nor authentication/freshness.
    """
    if type(poll) is not NintendoHTTPPoll:
        raise NintendoLoadError('Expected an explicit Nintendo HTTP poll projection')
    _i32(poll.raw_poll_result)
    _i32(poll.manager_result)
    if type(poll.native_data_phase_reached) is not bool:
        raise NintendoLoadError('Expected an explicit observed-phase predicate')
    state = _state(poll.state)
    if (not poll.native_data_phase_reached or poll.raw_poll_result != 0 or poll.manager_result != 0
            or state.word_04 not in (2, 3) or state.word_08 not in (3, 5)
            or state.skipped_input or state.copied_bytes == 0):
        raise NintendoLoadError('Supplied response has not reached a complete retained-data handoff')
    return inspect_japanese_list_download(csdata_payload, state.buffer[:state.copied_bytes],
                                           service_prefix=service_prefix, language_code=language_code)
