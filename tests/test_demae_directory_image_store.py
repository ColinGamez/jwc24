from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from PIL import Image

from tools.demae_directory_image_store import DirectoryImageStore, image_index


class CatalogImageTests(unittest.TestCase):
    def catalogs(self):
        return [{'provider': 'hotpepper', 'prefecture_id': f'JP-{n:02d}', 'restaurants': [
            {'id': f'hotpepper:J{n:09d}',
             'logo_url': f'https://imgfp.hotp.jp/IMGH/00/01/P{n:09d}/P{n:09d}_69.jpg'}]}
            for n in range(1, 48)]

    def test_all_prefectures_keep_own_source_image_mapping(self):
        index = image_index(self.catalogs())
        self.assertEqual(len(index), 47)
        self.assertEqual(len({row['prefecture'] for row in index.values()}), 47)
        self.assertEqual(len({row['source_url'] for row in index.values()}), 47)
        catalogs = self.catalogs()
        catalogs[-1]['restaurants'][0]['id'] = catalogs[0]['restaurants'][0]['id']
        with self.assertRaises(ValueError):
            image_index(catalogs)

    def test_fetch_once_persist_bytes_reopen_and_reject_tampering(self):
        buffer = BytesIO()
        Image.new('RGB', (8, 8)).save(buffer, format='JPEG')
        data = buffer.getvalue()
        requests = []
        def fetch(url):
            requests.append(url)
            return data
        with tempfile.TemporaryDirectory() as directory:
            store = DirectoryImageStore(self.catalogs(), directory, fetch=fetch)
            self.assertIsNone(store.get('hotpepper:J999999999'))
            self.assertEqual(requests, [])
            self.assertEqual(store.get('hotpepper:J000000010'), data)
            self.assertEqual(store.get('hotpepper:J000000010'), data)
            self.assertEqual(len(requests), 1)
            reopened = DirectoryImageStore(self.catalogs(), directory, fetch=fetch)
            self.assertEqual(reopened.get('hotpepper:J000000010'), data)
            self.assertEqual(len(requests), 1)
            (Path(directory) / 'J000000010.jpg').write_bytes(b'broken')
            with self.assertRaises(ValueError):
                reopened.get('hotpepper:J000000010')
            self.assertEqual(len(requests), 1)

    def test_missing_images_and_bad_downloads_do_not_create_fake_assets(self):
        catalogs = self.catalogs()
        catalogs[0]['restaurants'][0]['logo_url'] = None
        with tempfile.TemporaryDirectory() as directory:
            store = DirectoryImageStore(catalogs, directory, fetch=lambda url: b'invalid')
            self.assertIsNone(store.get('hotpepper:J000000001'))
            with self.assertRaises(OSError):
                store.get('hotpepper:J000000002')
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_provider_no_image_logo_uses_restaurant_source_photo(self):
        catalogs = self.catalogs()
        row = catalogs[0]['restaurants'][0]
        row['photo_url'] = row['logo_url']
        row['logo_url'] = 'https://imgfp.hotp.jp/SYS/cmn/images/common/diary/custom/m30_img_noimage.gif'
        source = image_index(catalogs)[row['id']]
        self.assertEqual(source['source_url'], row['photo_url'])
        self.assertEqual(source['source_field'], 'photo_url')
