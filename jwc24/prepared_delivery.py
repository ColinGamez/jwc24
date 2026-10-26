"""Shared route ownership checks for explicitly prepared channel snapshots.

This does not load publications, read keys, provision tasks or create listeners.
The same contract is used by offline preflight and the download server.
"""
from __future__ import annotations

from .hbnj_publication import HBNJRouteSnapshot, HBNJPublicationError
from .news_publication import NewsPublication


class PreparedDeliveryError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def snapshot_tasks(manifests, *, news_publication=None, hbnj_snapshot=None, now=None):
    """Return HBNJ tasks supplied by the validated snapshot, by identity.

    News files already contain their signed envelope and have no generic
    manifest-task substitute. News validity on each request remains the News
    application's responsibility; preflight also checks its explicit clock.
    """
    tasks = tuple(task for manifest in manifests for task in manifest.tasks)
    assets = tuple(asset for manifest in manifests for asset in manifest.assets)
    hbnj_items = {}
    if hbnj_snapshot is not None:
        if type(hbnj_snapshot) is not HBNJRouteSnapshot:
            raise PreparedDeliveryError('hbnj_snapshot_invalid',
                                        'HBNJ serving needs a validated loaded snapshot')
        try:
            hbnj_snapshot.metadata()
            hbnj_snapshot.raw_payload('/header.bin', now=now)
        except HBNJPublicationError:
            raise PreparedDeliveryError('hbnj_snapshot_invalid_or_expired',
                                        'HBNJ snapshot is unprepared or no longer current') from None
        owners = [manifest for manifest in manifests if manifest.channel_id == 'HBNJ']
        if len(owners) != 1 or owners[0].title_id != 0x0001000148424E4A:
            raise PreparedDeliveryError('hbnj_snapshot_owner_mismatch',
                                        'HBNJ snapshot requires its verified title manifest')
        hbnj_items = {task.filename: task for task in owners[0].tasks
                      if task.filename in {'header.bin', 'epg.bin', 'str.bin'}}
        if (set(hbnj_items) != {'header.bin', 'epg.bin', 'str.bin'}
                or any(item.compression != 'nintendo-lz10' or item.envelope != 'wc24-aes-ofb'
                       for item in hbnj_items.values())):
            raise PreparedDeliveryError('hbnj_snapshot_transport_mismatch',
                                        'HBNJ snapshot requires the original three task transport modes')
        if any(task.route.rsplit('/', 1)[-1] in hbnj_items
               and all(task is not owned for owned in hbnj_items.values()) for task in tasks):
            raise PreparedDeliveryError('hbnj_snapshot_route_conflict',
                                        'Another manifest task conflicts with the HBNJ route family')
    if news_publication is not None:
        if type(news_publication) is not NewsPublication or not news_publication.is_prepared():
            raise PreparedDeliveryError('news_publication_invalid',
                                        'News serving needs an explicitly prepared publication')
        prefix = news_publication.route_prefix + '/'
        names = {f'news.bin.{slot:02d}' for slot in range(24)}
        if (any(task.route.startswith(prefix) for task in tasks)
                or any(item.filename in names for item in (*tasks, *assets))):
            raise PreparedDeliveryError('news_publication_route_conflict',
                                        'News publication routes conflict with manifest payloads')
    return hbnj_items
