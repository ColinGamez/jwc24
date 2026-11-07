"""Explicit original HATJ request setup/submission, without SDK or network IO."""
from __future__ import annotations

from dataclasses import dataclass, field
import struct

from .nintendo_http import _u32, _i32
from .nintendo_listdata import MAX_LIST_BYTES
from .nintendo_load import NintendoLoadError
from .nintendo_manager import _error_detail

STORAGE_BYTES = 0x2D3C
INNER = 0x2C10
CREATE, DESTROY, HEADER = 0x802AA180, 0x802A9AB0, 0x802AA200
CONFIGURE, SELECT, OPTION = 0x802AA7D0, 0x802AA900, 0x802AA600
SEND, LAST_ERROR, TICK = 0x802A9D40, 0x802AA150, 0x8021F810
_SDK = frozenset((CREATE, DESTROY, HEADER, CONFIGURE, SELECT, OPTION, SEND, LAST_ERROR))
MAX_SDK_RESULTS = 16
MAX_TICK_RESULTS = 1


@dataclass(frozen=True)
class NintendoRequestState:
    object_word: int = field(repr=False)
    storage: bytes = field(repr=False)
    shared_word: int = field(repr=False)
    retry_word: int = field(repr=False)


@dataclass(frozen=True)
class NintendoRequestInputs:
    reference: bytes = field(repr=False)
    receive_word: int = field(repr=False)
    capacity_word: int = field(repr=False)
    callback_word: int = field(repr=False)
    callback_context_word: int = field(repr=False)
    user_agent: bytes = field(repr=False)
    referer: bytes | None = field(repr=False)
    range_word: int = field(repr=False)


@dataclass(frozen=True)
class NintendoRequestCall:
    """Observed call projection; SELECT uses normalized (handle, table slot).

    SELECT does not expose or label the original opaque resource pointer/size.
    The native verifier separately checks those indexed original table words.
    """
    address: int
    arguments: tuple = field(repr=False)
    returned_words: tuple[int, ...] = field(repr=False)


@dataclass(frozen=True)
class NintendoRequestResult:
    state: NintendoRequestState = field(repr=False)
    result: int = field(repr=False)
    calls: tuple[NintendoRequestCall, ...] = field(repr=False)
    entry: str

    def metadata(self):
        return {'entry': self.entry, 'numeric_result_zero': self.result == 0,
                'sdk_boundary_calls': sum(x.address != TICK for x in self.calls),
                'tick_boundary_calls': sum(x.address == TICK for x in self.calls),
                'sdk_outcomes_are_caller_assertions': True,
                'sdk_async_state_or_resource_use_verified': False,
                'network_authentication_or_catalog_completion_verified': False,
                'native_payload_or_request_published': False}


def _state(state):
    if type(state) is not NintendoRequestState:
        raise NintendoLoadError('Expected an explicit Nintendo request snapshot')
    _u32(state.object_word)
    if state.object_word == 0 or state.object_word + STORAGE_BYTES > 0x100000000:
        raise NintendoLoadError('Request object word exceeds the bounded native subset')
    if type(state.storage) is not bytes or len(state.storage) != STORAGE_BYTES:
        raise NintendoLoadError('Expected exact opaque request-manager storage')
    _u32(state.shared_word)
    _i32(state.retry_word)
    if state.retry_word not in (-1, 0, 1):
        raise NintendoLoadError('Retry selector exceeds the reviewed table subset')
    return state


def _cstring(value, maximum, *, nonempty=False):
    if (type(value) is not bytes or len(value) > maximum or b'\0' in value
            or nonempty and not value):
        raise NintendoLoadError('Expected explicitly supplied bounded string bytes')
    return value


def _inputs(inputs):
    if type(inputs) is not NintendoRequestInputs:
        raise NintendoLoadError('Expected explicit Nintendo request inputs')
    _cstring(inputs.reference, 511, nonempty=True)
    _cstring(inputs.user_agent, 4096)
    if inputs.referer is not None:
        _cstring(inputs.referer, 4096)
    for name in ('receive_word', 'capacity_word', 'callback_word', 'callback_context_word', 'range_word'):
        _u32(getattr(inputs, name))
    if inputs.capacity_word > MAX_LIST_BYTES:
        raise NintendoLoadError('Receive capacity exceeds the bounded backend subset')
    return inputs


class _Execution:
    def __init__(self, state, sdk_results, tick_words):
        self.before = _state(state)
        self.data = bytearray(state.storage)
        self.shared = state.shared_word
        self.calls = []
        if (type(sdk_results) is not tuple or type(tick_words) is not tuple
                or len(sdk_results) > MAX_SDK_RESULTS or len(tick_words) > MAX_TICK_RESULTS):
            raise NintendoLoadError('Expected explicit ordered SDK and tick outcomes')
        for pair in sdk_results:
            if type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not int or pair[0] not in _SDK:
                raise NintendoLoadError('Unsupported SDK boundary outcome')
            _u32(pair[1])
        for pair in tick_words:
            if type(pair) is not tuple or len(pair) != 2:
                raise NintendoLoadError('Expected explicit two-word ticks')
            for value in pair:
                _u32(value)
        self.sdk, self.ticks = list(sdk_results), list(tick_words)

    def word(self, offset):
        return struct.unpack_from('>I', self.data, offset)[0]

    def store(self, offset, value):
        struct.pack_into('>I', self.data, offset, value & 0xFFFFFFFF)

    def sdk_call(self, address, *arguments):
        if not self.sdk or self.sdk[0][0] != address:
            raise NintendoLoadError('Supplied SDK outcome sequence does not match the observed branch')
        _, value = self.sdk.pop(0)
        self.calls.append(NintendoRequestCall(address, tuple(arguments), (value,)))
        return value

    def clear_headers(self):
        for offset in (0x18, 0x58, 0x78, 0xB8):
            self.data[INNER + offset] = 0

    def reset_inner(self):
        for offset in (0, 4, 8, 12, 0x10, 0x14, 0x118, 0x120):
            self.store(INNER + offset, 0)
        self.clear_headers()

    def cleanup(self):
        handle = self.word(INNER)
        if handle:
            destroyed = self.sdk_call(DESTROY, handle)
            self.reset_inner()
            if destroyed:
                self.store(INNER + 4, destroyed)
                return False
        return True

    def header(self, name, value, offset):
        copied = value[:63]
        self.data[INNER + offset:INNER + offset + len(copied) + 1] = copied + b'\0'
        handle = self.word(INNER)
        if handle and (name != b'Range' or copied):
            if self.sdk_call(HEADER, handle, name, copied):
                self.sdk_call(DESTROY, handle)
                self.store(INNER, 0)
                self.clear_headers()
                return 6
        return 0

    def submit(self):
        if self.shared not in (1, 3, 5):
            return 7
        sent = self.sdk_call(SEND, self.word(INNER))
        if sent:
            self.store(INNER + 0x124, _error_detail(sent))
            self.cleanup()
            self.store(INNER + 4, sent)
            return 3
        self.shared = 2
        if not self.ticks:
            raise NintendoLoadError('Missing explicit tick boundary outcome')
        ticks = self.ticks.pop(0)
        self.calls.append(NintendoRequestCall(TICK, (), ticks))
        for offset, word in ((0xF8, ticks[0]), (0xFC, ticks[1]), (0x108, ticks[0]),
                             (0x10C, ticks[1]), (0x110, 0), (0x114, 0)):
            self.store(INNER + offset, word)
        return 0

    def prepare(self, inputs):
        inputs = _inputs(inputs)
        self.store(0x29AC, inputs.callback_word)
        self.store(0x29B0, inputs.callback_context_word)
        if self.shared not in (1, 3, 5) or inputs.capacity_word == 0:
            return self.failed(7)
        if not self.cleanup():
            return self.failed(3)
        for offset, value in ((0x10, 0), (0x14, 0), (8, 0x80026AE0),
                              (12, self.before.object_word), (0x118, 0), (0x120, 200), (0x11C, 0)):
            self.store(INNER + offset, value)
        handle = self.sdk_call(CREATE, inputs.reference, 0, inputs.receive_word,
                                inputs.capacity_word, 0x80027E40, self.before.object_word + INNER)
        self.store(INNER, handle)
        if not handle:
            self.store(INNER + 0x124, _error_detail(self.sdk_call(LAST_ERROR)))
            return self.failed(5)
        self.store(INNER + 0x128, 0)
        self.sdk_call(CONFIGURE, handle)
        self.sdk_call(SELECT, handle, 0 if self.before.retry_word == -1 else self.before.retry_word)
        self.sdk_call(OPTION, handle, 4)
        # The initialized original getter limits its temporary buffer to 25
        # bytes including NUL. Device-derived generation is outside this API.
        result = self.header(b'User-Agent', inputs.user_agent[:24], 0x78)
        if result:
            return self.failed(result)
        if inputs.referer is not None:
            result = self.header(b'Referer', inputs.referer, 0xB8)
            if result:
                return self.failed(result)
        if inputs.range_word:
            result = self.header(b'Range', b'bytes=' + str(inputs.range_word).encode('ascii') + b'-', 0x58)
            if result:
                return self.failed(result)
        result = self.submit()
        return self.failed(result) if result else 0

    def failed(self, stage):
        self.store(0, self.word(INNER + 0x124))
        return -109 if 2 <= stage <= 7 or stage == 9 else -209 if stage == 8 else 1 if stage == 1 else 0 if stage == 0 else -300

    def finish(self, result, entry):
        if self.sdk or self.ticks:
            raise NintendoLoadError('Unused supplied SDK or tick outcomes')
        state = NintendoRequestState(self.before.object_word, bytes(self.data), self.shared, self.before.retry_word)
        return NintendoRequestResult(state, result, tuple(self.calls), entry)


def prepare_request(state: NintendoRequestState, inputs: NintendoRequestInputs, *,
                    sdk_results: tuple[tuple[int, int], ...],
                    tick_words: tuple[tuple[int, int], ...]) -> NintendoRequestResult:
    """Project complete setup using supplied SDK returns, never perform IO.

    SDK boundaries are assumed to return without mutating application RAM or
    invoking asynchronous callbacks. Concurrent state production is unproved.
    """
    execution = _Execution(state, sdk_results, tick_words)
    return execution.finish(execution.prepare(inputs), 'prepare')


def submit_request(state: NintendoRequestState, *, sdk_results: tuple[tuple[int, int], ...],
                   tick_words: tuple[tuple[int, int], ...]) -> NintendoRequestResult:
    """Project direct inner submission, keeping its stage result unnormalized."""
    execution = _Execution(state, sdk_results, tick_words)
    return execution.finish(execution.submit(), 'submit')
