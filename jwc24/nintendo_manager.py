"""Original HATJ manager callback frame and its supplied HTTP-state handoff.

Inner SDK state is supplied, not produced by verified transport. Native numeric
words retain their offsets; a delivered non-error frame proves no catalog trust.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .nintendo_http import NintendoHTTPCallback, NintendoHTTPState, _state, _u32, _signed, apply_http_callback
from .nintendo_listdata import MAX_LIST_BYTES
from .nintendo_load import NintendoLoadError


@dataclass(frozen=True)
class NintendoManagerState:
    manager_present: bool
    callback_present: bool
    callback_context_word: int = field(repr=False)
    shared_word: int = field(repr=False)
    word_2c20: int = field(repr=False)
    error_word_2d28: int = field(repr=False)
    detail_word_2d2c: int = field(repr=False)
    response_word_2d30: int = field(repr=False)
    flag_word_2d38: int = field(repr=False)


def _manager(value):
    if type(value) is not NintendoManagerState:
        raise NintendoLoadError('Expected an explicit Nintendo manager snapshot')
    if type(value.manager_present) is not bool or type(value.callback_present) is not bool:
        raise NintendoLoadError('Expected explicit manager and callback presence')
    for name in ('callback_context_word', 'shared_word', 'word_2c20', 'error_word_2d28',
                 'detail_word_2d2c', 'response_word_2d30', 'flag_word_2d38'):
        _u32(getattr(value, name))
    return value


def _error_detail(word):
    signed = _signed(word)
    if signed == -1:
        return 260001
    if 1 <= signed <= 13 or signed == 15:
        return 260000 + 100 * signed
    return 0


def _inner_detail(word):
    signed = _signed(word)
    return 261400 - signed if -16 <= signed <= 0 and signed != -4 else 0


@dataclass(frozen=True)
class NintendoManagerFrame:
    chunk: bytes = field(repr=False)
    word_08: int = field(repr=False)
    word_0c: int = field(repr=False)
    word_10: int = field(repr=False)
    word_14: int = field(repr=False)
    callback_context_word: int = field(repr=False)

    def metadata(self):
        return {'received_bytes': len(self.chunk),
                'callback_context_present': self.callback_context_word != 0,
                'derived_error_word_zero': self.word_10 == 0,
                'inner_state_independently_verified': False,
                'network_authentication_or_catalog_completion_verified': False}


def build_manager_frame(manager: NintendoManagerState, chunk: bytes) -> NintendoManagerFrame | None:
    """Project 0x80026AE0/26B10; absence means no callback was invoked.

    Missing manager or callback does not become a successful empty delivery.
    The downstream callback's null context is preserved in a present frame.
    """
    manager = _manager(manager)
    if type(chunk) is not bytes or len(chunk) > MAX_LIST_BYTES:
        raise NintendoLoadError('Callback bytes exceed the bounded local subset')
    if not manager.manager_present or not manager.callback_present:
        return None
    error = detail = 0
    if manager.error_word_2d28 not in (0, 8):
        detail = (_inner_detail(manager.detail_word_2d2c) if manager.error_word_2d28 == 14
                  else _error_detail(manager.error_word_2d28))
        error = -110 if manager.flag_word_2d38 == 1 else -109
    elif not 200 <= _signed(manager.response_word_2d30) <= 299:
        response = manager.response_word_2d30
        if response == 503:
            error = -107
        elif response == 404:
            error = -108
        elif response in (304, 401, 403, 500):
            error = -209
        else:
            error = -110 if manager.flag_word_2d38 == 1 else -109
        detail = (response + 268000) & 0xFFFFFFFF
    return NintendoManagerFrame(chunk, manager.shared_word, manager.word_2c20,
                                error & 0xFFFFFFFF, detail, manager.callback_context_word)


@dataclass(frozen=True)
class NintendoManagerDelivery:
    state: NintendoHTTPState = field(repr=False)
    frame: NintendoManagerFrame | None = field(repr=False)
    callback: NintendoHTTPCallback | None = field(repr=False)

    def metadata(self):
        return {'manager_callback_invoked': self.frame is not None,
                'http_callback_consumed': self.callback is not None,
                'received_bytes': len(self.frame.chunk) if self.frame is not None else 0,
                'retained_bytes': self.callback.retained_bytes if self.callback is not None else 0,
                'input_skipped': self.state.skipped_input,
                'retry_scheduled': self.callback.retry_scheduled if self.callback is not None else False,
                'inner_state_independently_verified': False,
                'network_authentication_or_catalog_completion_verified': False}


def apply_manager_callback(state: NintendoHTTPState, manager: NintendoManagerState,
                           chunk: bytes, *, loader_context_word: int) -> NintendoManagerDelivery:
    """Compose the manager relay with its configured original HTTP consumer.

    The supplied context word must identify this supplied loader snapshot.
    A different nonzero context cannot be silently redirected to this state.
    Zero context executes the original wrapper's bypass rather than its body.
    """
    state = _state(state)
    _u32(loader_context_word)
    if loader_context_word == 0:
        raise NintendoLoadError('Expected an explicit nonzero loader context word')
    frame = build_manager_frame(manager, chunk)
    callback = None
    if frame is not None and frame.callback_context_word:
        if frame.callback_context_word != loader_context_word:
            raise NintendoLoadError('Callback context does not identify the supplied loader state')
        callback = apply_http_callback(state, frame.chunk, word_08=frame.word_08,
                                       word_0c=frame.word_0c, word_10=frame.word_10,
                                       word_14=frame.word_14)
        state = callback.state
    return NintendoManagerDelivery(state, frame, callback)
