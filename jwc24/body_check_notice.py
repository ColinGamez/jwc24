"""Observed HFNJ header-gate decisions leading to an existing update notice.

No header words are renamed version fields, and no original text or UI asset is
replaced. This is an offline decision/inspection handoff, not a renderer.
"""
from dataclasses import dataclass, field

from .body_check import MAX_DATASET_BYTES
from .body_check_completion import DatasetHeaderGate, inspect_dataset_header_gate

UPDATE_NOTICE_MESSAGE_ID = 0x754C
UPDATE_NOTICE_VARIANT = 0


class BodyCheckNoticeError(ValueError):
    pass


class BodyCheckNoticeUnsupported(BodyCheckNoticeError):
    pass


@dataclass(frozen=True)
class NoticeContext:
    gate_context_word8: int = field(repr=False)
    secondary_context_word8: int = field(repr=False)
    manager_latched_flag: bool
    transition_dialog_busy: bool
    advance_selector: bool
    selector_dialog_busy: bool | None


def _validate_context(context):
    if type(context) is not NoticeContext:
        raise BodyCheckNoticeError('An explicit native notice context is required')
    if any(type(value) is not int or not 0 <= value <= 0xFFFFFFFF
           for value in (context.gate_context_word8, context.secondary_context_word8)):
        raise BodyCheckNoticeError('Expected explicit unsigned context words')
    if any(type(value) is not bool for value in (context.manager_latched_flag,
           context.transition_dialog_busy, context.advance_selector)):
        raise BodyCheckNoticeError('Expected explicit context predicates')
    if (context.advance_selector and type(context.selector_dialog_busy) is not bool
            or not context.advance_selector and context.selector_dialog_busy is not None):
        raise BodyCheckNoticeError('Selector-phase state must be supplied only for an explicit advance')


def _header_needed(context):
    _validate_context(context)
    if context.gate_context_word8 & 0x300:
        return False
    if (context.manager_latched_flag or context.secondary_context_word8 & 0x1000
            and not context.secondary_context_word8 & 0x10):
        raise BodyCheckNoticeUnsupported('The separate native context/error handler is outside this handoff')
    return True


@dataclass(frozen=True)
class NoticeDecision:
    header_gate_evaluated: bool
    next_state: int | None
    selector: int | None
    control: int | None
    message_id: int | None
    message_variant: int | None
    secondary_context_call_requested: bool
    dialog_close_requested: bool
    selector_advanced: bool

    def metadata(self):
        return {'header_gate_evaluated': self.header_gate_evaluated,
                'next_native_state': self.next_state, 'native_selector': self.selector,
                'native_control': self.control, 'requested_message_id': self.message_id,
                'requested_message_variant': self.message_variant,
                'secondary_context_call_requested': self.secondary_context_call_requested,
                'dialog_close_requested': self.dialog_close_requested,
                'selector_advanced': self.selector_advanced,
                'message_rendered': False, 'native_ui_verified': False,
                'header_word_meanings_verified': False,
                'dataset_freshness_or_authentication_verified': False,
                'profile_or_live_state_modified': False}


def plan_header_notice(pair_gate_result: bool | None, *, context: NoticeContext) -> NoticeDecision:
    """Plan the observed prefix and optional explicit later selector phase.

    Each UI-busy predicate is sampled at its own phase. The selector is not
    silently advanced in the same frame, and a close request does not mean that
    the dialog has already closed. Context/error paths outside this slice reject
    explicitly rather than acquiring an invented screen or result.
    """
    if pair_gate_result is not None and type(pair_gate_result) is not bool:
        raise BodyCheckNoticeError('Expected an explicit opaque-pair predicate or no evaluation')
    if not _header_needed(context):
        return NoticeDecision(False, None, None, None, None, None, False, False, False)
    if pair_gate_result is None:
        raise BodyCheckNoticeError('The selected path requires an explicit header-pair result')
    if not pair_gate_result:
        return NoticeDecision(True, 0x2B, None, None, None, None, True, False, False)
    advanced = context.advance_selector
    requested = advanced and not context.selector_dialog_busy
    return NoticeDecision(True, 0x2D if requested else 0x33, 0x2D, 1,
                          UPDATE_NOTICE_MESSAGE_ID if requested else None,
                          UPDATE_NOTICE_VARIANT if requested else None,
                          False, context.transition_dialog_busy, advanced)


@dataclass(frozen=True)
class DatasetNoticeInspection:
    header: DatasetHeaderGate | None
    decision: NoticeDecision

    def metadata(self):
        return {**(self.header.metadata() if self.header is not None else {}),
                **self.decision.metadata(), 'header_crc_checked': self.header is not None,
                'native_message_asset_loaded': False}


def inspect_dataset_notice(data: bytes, *, context: NoticeContext) -> DatasetNoticeInspection:
    """Inspect a bounded supplied plaintext header only if its path consumes it.

    A consumed header must pass the existing sixteen-byte/CRC safety policy.
    That is stricter than the isolated original predicate; a native unchecked
    buffer is never promoted to an authenticated or current dataset here.
    """
    if type(data) is not bytes or len(data) > MAX_DATASET_BYTES:
        raise BodyCheckNoticeError('Expected bounded immutable dataset bytes')
    if not _header_needed(context):
        return DatasetNoticeInspection(None, plan_header_notice(None, context=context))
    header = inspect_dataset_header_gate(data)
    return DatasetNoticeInspection(header, plan_header_notice(header.gate_result, context=context))
