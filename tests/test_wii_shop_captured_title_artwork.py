import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from jwc24.wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from jwc24.wii_shop_title_artwork import TitleArtwork
from tests.test_wii_shop_browse import record
from tools.build_wii_shop_captured_title_artwork import PRIVATE, build


@unittest.skipUnless(importlib.util.find_spec('PIL'), 'Image validation requires Pillow')
class CapturedTitleArtworkBuilderTests(unittest.TestCase):
    def fixture(self, root):
        from PIL import Image
        identifier = '0001000141424344'
        catalog = root/'catalog.json'
        catalog.write_text(json.dumps({'records':[record()]}),encoding='utf-8')
        capture = root/'capture'
        (capture/'blobs').mkdir(parents=True)
        files, images, details = [], {}, {}
        for role, number, color, proof in ((images,'0000','red','reference_catalog_sha256'),
                                            (details,'0005','blue','reference_detail_sha256')):
            stream = BytesIO()
            Image.new('RGB',(64,48),color).save(stream,format='GIF')
            data = stream.getvalue()
            fingerprint = hashlib.sha256(data).hexdigest()
            (capture/'blobs'/fingerprint).write_bytes(data)
            member = 'oss-auth.shop.wii.com/oss/ccs/'+identifier+'/FFFD'+number
            files.append({'member':member,'sha256':fingerprint,'bytes':len(data),'file':'blobs/'+fingerprint})
            role[identifier] = {'member':member,proof:'a'*64}
        (capture/'manifest.private.json').write_text(json.dumps(dict(source=SOURCE,archive_sha1=ARCHIVE_SHA1,files=files)))
        requests = root/'requests.json'
        requests.write_text(json.dumps(dict(source=SOURCE,archive_sha1=ARCHIVE_SHA1,
            catalog_sha256=hashlib.sha256(catalog.read_bytes()).hexdigest(),images=images,detail_images=details)))
        return identifier,catalog,capture,requests

    def test_builder_preserves_role_bytes_and_refuses_changed_capture(self):
        PRIVATE.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=PRIVATE) as directory:
            root = Path(directory)
            identifier,catalog,capture,requests = self.fixture(root)
            report = build(capture,catalog,root/'pack',requests)
            self.assertEqual((report['catalog_images'],report['detail_images']),(1,1))
            pack = TitleArtwork(root/'pack',hashlib.sha256(catalog.read_bytes()).hexdigest())
            self.assertNotEqual(pack.images[identifier],pack.detail_images[identifier])
            source = next((capture/'blobs').iterdir())
            source.write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError,'fingerprint'):
                build(capture,catalog,root/'changed',requests)
            self.assertFalse((root/'changed').exists())

    def test_builder_requires_the_correct_page_proof_for_each_role(self):
        with tempfile.TemporaryDirectory(dir=PRIVATE) as directory:
            root = Path(directory)
            identifier,catalog,capture,requests = self.fixture(root)
            document = json.loads(requests.read_text())
            row = document['images'][identifier]
            row['reference_detail_sha256'] = row.pop('reference_catalog_sha256')
            requests.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError,'page reference'):
                build(capture,catalog,root/'pack',requests)
            self.assertFalse((root/'pack').exists())
