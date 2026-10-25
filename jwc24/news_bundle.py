"""Check explicit cross-buffer News references without acquiring or serving data."""
from dataclasses import dataclass

from .news import (ENVELOPE_SIZE, HEADER_SIZE, MAX_ENVELOPE_BYTES, MAX_RAW_BYTES, NONE_INDEX, NewsFormatError,
                   inspect_news, inspect_news_envelope)

SLOT_COUNT = 24
MAX_BUNDLE_BYTES = 32 * 1024 * 1024  # Local tooling policy, not native capacity.


@dataclass(frozen=True)
class NewsBundleInspection:
    buffers: int
    distinct_snapshots: int
    repeated_snapshots: int
    articles: int
    cross_buffer_topic_references: int
    cross_buffer_image_references: int

    def metadata(self):
        return {
            'buffers': self.buffers, 'distinct_snapshots': self.distinct_snapshots,
            'repeated_snapshots': self.repeated_snapshots,
            'distinct_snapshot_articles': self.articles,
            'cross_buffer_topic_references': self.cross_buffer_topic_references,
            'cross_buffer_image_references': self.cross_buffer_image_references,
            'cross_buffer_references_checked': True,
            'time_slot_mapping_or_24_hour_coverage_verified': False,
            'signatures_checked': False, 'current_validity_checked': False,
            'publisher_or_media_content_verified': False,
            'native_delivery_or_rendering_verified': False,
            'scope': 'all references in the explicitly supplied buffer set; local strict policy',
        }


def inspect_news_bundle(buffers, *, enveloped: bool = False) -> NewsBundleInspection:
    """Resolve topic→timestamp/article and article→timestamp/image references.

    Exactly 24 slots reflects the examined native validator's input shape, not
    a recovered task registration or hourly URL mapping. Identical snapshots
    may repeat, as in native synthetic tests; repetition never proves time
    coverage. Conflicting bytes for one snapshot timestamp are ambiguous and
    rejected. Missing references fail rather than reproducing native pruning.
    """
    if (not isinstance(buffers, (tuple, list)) or len(buffers) != SLOT_COUNT
            or type(enveloped) is not bool):
        raise NewsFormatError('Expected exactly 24 explicit News buffer slots')
    maximum = MAX_ENVELOPE_BYTES if enveloped else MAX_RAW_BYTES
    total = decoded_total = 0
    for buffer in buffers:
        if not isinstance(buffer, bytes) or not 0 < len(buffer) <= maximum:
            raise NewsFormatError('News bundle slot violates local byte bounds')
        total += len(buffer)
        if total > MAX_BUNDLE_BYTES:
            raise NewsFormatError('News bundle exceeds its local aggregate byte limit')
        if enveloped:
            if len(buffer) < ENVELOPE_SIZE + 4 or buffer[ENVELOPE_SIZE] != 0x10:
                raise NewsFormatError('News bundle envelope lacks the reviewed LZ10 header')
            size = int.from_bytes(buffer[ENVELOPE_SIZE + 1:ENVELOPE_SIZE + 4], 'little')
            if not HEADER_SIZE <= size <= MAX_RAW_BYTES:
                raise NewsFormatError('News bundle advertised decoded size violates local bounds')
        else:
            size = len(buffer)
        decoded_total += size
        if decoded_total > MAX_BUNDLE_BYTES:
            raise NewsFormatError('News bundle exceeds its local aggregate decoded byte limit')
    inspect = inspect_news_envelope if enveloped else inspect_news
    snapshots = {}
    for buffer in buffers:
        item = inspect(buffer)
        previous = snapshots.get(item.updated_timestamp)
        if previous is not None and previous.buffer_sha256 != item.buffer_sha256:
            raise NewsFormatError('News bundle has conflicting data for one snapshot timestamp')
        snapshots[item.updated_timestamp] = item
    locales = {(item.country_code, item.language_code) for item in snapshots.values()}
    if len(locales) != 1:
        raise NewsFormatError('News bundle mixes country or language fields')
    article_ids = {timestamp: {article.identifier for article in item.articles}
                   for timestamp, item in snapshots.items()}
    topic_links = image_links = 0
    for timestamp, item in snapshots.items():
        for target_time, identifier in item.topic_links:
            if target_time not in article_ids or identifier not in article_ids[target_time]:
                raise NewsFormatError('News bundle has an unresolved topic article reference')
            topic_links += target_time != timestamp
        for article in item.articles:
            if not article.picture_timestamp or article.picture_index == NONE_INDEX:
                continue
            target = snapshots.get(article.picture_timestamp)
            if target is None or article.picture_index >= target.images:
                raise NewsFormatError('News bundle has an unresolved article image reference')
            image_links += article.picture_timestamp != timestamp
    return NewsBundleInspection(len(buffers), len(snapshots), len(buffers) - len(snapshots),
                                sum(len(item.articles) for item in snapshots.values()),
                                topic_links, image_links)
