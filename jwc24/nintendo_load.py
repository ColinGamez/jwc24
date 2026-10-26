"""Explicit Nintendo Channel language gate and offline ListData handoff.

No reference is fetched, native object installed, catalog synthesized or service
authentication inferred. Existing framing/record decoders remain independent.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .nintendo_csdata import CSDataInspection, decompress_csdata, inspect_csdata
from .nintendo_listdata import NintendoListInspection, inspect_listdata
from .nintendo_references import NintendoListReference, build_japanese_list_reference


class NintendoLoadError(ValueError):
    """Explicit input is outside the supported offline load handoff."""


@dataclass(frozen=True)
class NintendoListLoadPlan:
    csdata: CSDataInspection = field(repr=False)
    accepted_language_entries: tuple[int, ...] = field(repr=False)
    language_eligible: bool
    reference: NintendoListReference | None = field(repr=False)

    def metadata(self):
        return {
            'csdata_framing_and_crc_checked': True,
            'channel_language_eligibility_checked': True,
            'accepted_language_entries': len(self.accepted_language_entries),
            'language_eligible': self.language_eligible,
            'follow_on_reference_prepared': self.reference is not None,
            'endpoint_authorized': False,
            'catalog_downloaded': False,
            'native_io_or_ui_verified': False,
        }


def plan_japanese_list_load(csdata_payload: bytes, *, service_prefix: bytes,
                            language_code: int) -> NintendoListLoadPlan:
    """Apply the actual pre-download language predicate to explicit CSData.

    Native accessors count the prefix of bytes +0x18..+0x27 that are below seven,
    stopping at the first other value. Order and duplicate entries are retained.
    The configured language is a supplied byte; it is never inferred from region.
    """
    if type(language_code) is not int or not 0 <= language_code <= 255:
        raise NintendoLoadError('Expected an explicit configured language byte')
    if (type(service_prefix) is not bytes or not 0 < len(service_prefix) < 512
            or b'\0' in service_prefix):
        raise NintendoLoadError('Expected a bounded explicit service prefix without NUL')
    csdata = inspect_csdata(csdata_payload)
    raw, _compression = decompress_csdata(csdata_payload)
    languages = []
    for value in raw[0x18:0x28]:
        if value >= 7:
            break
        languages.append(value)
    eligible = language_code in languages
    reference = (build_japanese_list_reference(csdata_payload, service_prefix=service_prefix,
                                               language_code=language_code) if eligible else None)
    return NintendoListLoadPlan(csdata, tuple(languages), eligible, reference)


@dataclass(frozen=True)
class NintendoListLoadInspection:
    plan: NintendoListLoadPlan = field(repr=False)
    listdata: NintendoListInspection = field(repr=False)

    def metadata(self):
        return {
            'language_gate': self.plan.metadata(),
            'listdata': self.listdata.metadata(),
            'bounded_offline_handoff_checked': True,
            'download_reference_or_response_origin_verified': False,
            'authentication_or_freshness_verified': False,
            'native_publication_or_browsing_verified': False,
        }


def inspect_japanese_list_download(csdata_payload: bytes, list_payload: bytes, *,
                                   service_prefix: bytes, language_code: int) -> NintendoListLoadInspection:
    """Gate a supplied list through the existing bounded record decoder.

    The payload is exact supplied data, not the padded full native allocation.
    A failed language gate cannot become an empty-catalog or successful load.
    This function does not establish that the bytes came from the planned URL.
    """
    plan = plan_japanese_list_load(csdata_payload, service_prefix=service_prefix,
                                   language_code=language_code)
    if not plan.language_eligible:
        raise NintendoLoadError('Configured language is absent from the accepted CSData prefix')
    return NintendoListLoadInspection(plan, inspect_listdata(list_payload))
