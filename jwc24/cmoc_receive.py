"""Configured CMOC receive geometry, separate from crypto and SDK transport.

The original setup projects a capacity without checking its embedded storage.
This composition gate checks that capacity and each supplied backing extent.
It neither invents padding nor changes the original setup projection.
"""
from dataclasses import dataclass

from .cmoc_request_setup import RequestSetup


WIRE_BYTES = 0x440
TRANSFORM_BYTES = 0x400


def _size(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('Invalid explicit CMOC receive extent')
    return value


@dataclass(frozen=True)
class ConfiguredReceiveLayout:
    resolved_hash_span_size: int
    wire_prefix_size: int
    transform_offset: int
    advertised_capacity: int

    def __post_init__(self):
        _size(self.resolved_hash_span_size, 64)
        _size(self.wire_prefix_size, 64)
        if (type(self.transform_offset) is not int
                or self.transform_offset != self.resolved_hash_span_size + self.wire_prefix_size
                or self.transform_offset > WIRE_BYTES - TRANSFORM_BYTES
                or type(self.advertised_capacity) is not int
                or self.advertised_capacity != self.transform_offset + TRANSFORM_BYTES):
            raise ValueError('CMOC configured receive capacity exceeds its native storage')


@dataclass(frozen=True)
class TransformExtent:
    source_offset: int
    received_payload_bytes: int
    padded_transform_bytes: int
    required_backing_end: int


def check_configured_receive_layout(setup: RequestSetup, *,
                                    resolved_hash_span_size: int) -> ConfiguredReceiveLayout:
    """Compose an existing setup projection with the proved storage boundary.

    The supplied resolved word is not inferred from a digest algorithm. Real
    resource loading, hash/cipher setup and SDK acceptance remain separate.
    Raw/unconfigured requests have a different buffer and are not accepted.
    """
    if type(setup) is not RequestSetup or setup.configured is not True:
        raise ValueError('Explicit configured CMOC request setup required')
    if type(setup.retained_wire_prefix) is not bytes:
        raise ValueError('Explicit retained CMOC prefix required')
    _size(resolved_hash_span_size, 64)
    return ConfiguredReceiveLayout(resolved_hash_span_size, len(setup.retained_wire_prefix),
        resolved_hash_span_size + len(setup.retained_wire_prefix), setup.receive_capacity)


def check_transform_extent(layout: ConfiguredReceiveLayout, *, receive_end_offset: int,
                           backing_bytes: int) -> TransformExtent:
    """Require all actual rounded input bytes; never create zero padding.

    Extents are explicit caller assertions about existing initialized backing,
    not independent evidence of an SDK delivery or source capture. A partial
    block can require backing beyond the received endpoint. Supplying such
    bytes does not establish a valid cipher, checksum or response.
    """
    if type(layout) is not ConfiguredReceiveLayout:
        raise ValueError('Explicit checked CMOC receive layout required')
    _size(receive_end_offset, layout.advertised_capacity)
    _size(backing_bytes, WIRE_BYTES)
    if receive_end_offset < layout.transform_offset:
        raise ValueError('CMOC receive endpoint precedes its configured input')
    received = receive_end_offset - layout.transform_offset
    padded = (received + 15) & ~15
    end = layout.transform_offset + padded
    if padded > TRANSFORM_BYTES or end > backing_bytes:
        raise ValueError('CMOC receive lacks explicit rounded input backing')
    return TransformExtent(layout.transform_offset, received, padded, end)
