from io import BytesIO
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jwc24.wii_shop_title_artwork import TitleArtwork
from jwc24.wii_shop_artwork import Artwork
from jwc24.wii_shop_browse import Catalog
from jwc24.wii_shop_server import Application
from tools.import_wii_shop_title_artwork import image_info, fetch
from tests.test_wii_shop_browse import record


@unittest.skipUnless(importlib.util.find_spec('PIL'), 'Artwork image validation requires Pillow')
class ShopTitleArtworkTests(unittest.TestCase):
    identifier = '0001000141424344'

    def image(self):
        from PIL import Image
        stream = BytesIO()
        Image.new('RGB', (160, 120), 'white').save(stream, format='GIF')
        return stream.getvalue()

    def cache(self, root, data):
        identifier = self.identifier
        (root/(identifier+'.img')).write_bytes(data)
        row = dict(image_info(data), file=identifier+'.img', bytes=len(data),
                   sha256=hashlib.sha256(data).hexdigest(),
                   url='https://wiishopchannel.net/oss/ccs/'+identifier+'/FFFD0001')
        (root/'manifest.json').write_text(json.dumps({'source': 'https://wiishopchannel.net',
            'catalog_sha256': 'synthetic', 'images': {identifier: row}, 'missing': {}}))

    def test_image_route_is_bound_to_exact_title_and_missing_image_stays_transparent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = self.image()
            self.cache(root, data)
            pack = TitleArtwork(root, 'synthetic')
            self.assertEqual(pack.asset(pack.url(self.identifier)), (200, 'image/gif', data))
            self.assertEqual(pack.url('0001000141424345'), '/oss/oss/common/images/spacer.gif')
            self.assertEqual(pack.asset('/title-artwork/../keys.bin')[0], 404)

    def test_catalog_mismatch_and_file_drift_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.cache(root, self.image())
            with self.assertRaisesRegex(ValueError, 'source/catalog'):
                TitleArtwork(root, 'different')
            (root/(self.identifier+'.img')).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                TitleArtwork(root, 'synthetic')

    def test_html_empty_and_oversized_images_are_not_accepted(self):
        for data in (b'<html>not artwork</html>', b'', b'x'*(512*1024+1)):
            with self.assertRaises((OSError, ValueError)):
                image_info(data)
        self.assertEqual(image_info(self.image()), {'format': 'GIF', 'width': 160, 'height': 120})

    def test_request_url_cannot_be_supplied_as_a_title_id(self):
        with patch('tools.import_wii_shop_title_artwork.urlopen') as request:
            with self.assertRaises(ValueError):
                fetch('../../different')
            request.assert_not_called()

    def test_original_catalog_and_detail_slots_use_the_same_title_bound_image(self):
        original = Path('private/wii_shop/artwork-v2')
        if not (original/'manifest.json').is_file():
            self.skipTest('Private original page fixtures unavailable')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.cache(root, self.image())
            app = Application(Catalog([record()]), artwork=Artwork(original, root, 'synthetic'))
            for path in ('/catalog', '/title/'+self.identifier):
                with self.subTest(path=path):
                    body = app.get(path)[2]
                    self.assertIn(('/title-artwork/'+self.identifier).encode(), body)
            self.assertEqual(app.get('/title-artwork/'+self.identifier)[0], 200)
