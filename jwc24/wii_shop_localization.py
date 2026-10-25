"""Select reviewed Japanese controller artwork from the private collector pack.

This selects a Japanese asset variant, not a recovered Japanese B05 page. The
captured B05 used the matching English family. Original image bytes stay private.
"""
import hashlib
import struct


CONTROLLER_IMAGES = (
    ('/oss/oss/common/images/banner/controller_msg1_J_ja.gif', 3250,
     '222f22d5bf910030891152f304ac3e22eff397c6f79aa22d9749b7a6b5b52aa8'),
    ('/oss/oss/common/images/banner/controller_msg2_J_ja.gif', 3154,
     'aad1e109ef4997d1aac52ce2e63c009bfdcfc474abbee99a828e42b217f7509b'),
)


def controller_images(shared):
    """Return original Japanese normal/hover URLs after exact byte verification.

    ``shared`` is the existing CapturedScripts reader. This does not modify its
    resource map, decode/recreate an image, or change controller navigation.
    """
    urls = []
    for path, size, digest in CONTROLLER_IMAGES:
        resource = shared.shared.get(path)
        if not isinstance(resource, tuple) or len(resource) != 2:
            raise ValueError('Missing reviewed Japanese controller artwork')
        mime, data = resource
        if (mime != 'image/gif' or not isinstance(data, bytes) or len(data) != size
                or hashlib.sha256(data).hexdigest() != digest):
            raise ValueError('Japanese controller artwork fingerprint or size differs')
        if data[:6] not in (b'GIF87a', b'GIF89a') or struct.unpack('<HH', data[6:10]) != (77, 65):
            raise ValueError('Japanese controller artwork GIF dimensions differ')
        urls.append(shared.resource_url(path))
    return tuple(urls)
