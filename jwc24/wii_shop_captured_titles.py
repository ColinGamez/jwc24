"""Read verified historical detail/controller pages; no commerce execution."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import posixpath
import re
from urllib.parse import parse_qs

from .wii_shop_captured_catalog import page_tree
from .wii_shop_captured_scripts import ARCHIVE_SHA1, SOURCE
from .wii_shop_title_metadata import parse_detail

CONTROLLER_SCRIPT_URL = '/assets/captured/controller-mode.js'
CONTROLLER_REFERENCE_SHA256 = '3b7b8ba81514e9dad43575d9bc22cdbf2c7289f471286a6c7f4151f6c6162f04'
INDEX_REVISION = 2


def read_manifest(root):
    path = root/'manifest.private.json'
    if path.stat().st_size > 2*1024*1024:
        raise ValueError('Oversized title-page manifest')
    raw = path.read_bytes()
    document = json.loads(raw)
    if (document.get('source') != SOURCE or document.get('archive_sha1') != ARCHIVE_SHA1
            or len(document['files']) > 4000):
        raise ValueError('Unexpected title-page capture source')
    return document,hashlib.sha256(raw).hexdigest()


def read_page(root, row):
    digest = row['sha256']
    if not re.fullmatch('[0-9a-f]{64}',digest) or row['file'] != 'blobs/'+digest:
        raise ValueError('Unexpected title-page fingerprint/path')
    local = (root/row['file']).resolve()
    if not local.is_relative_to(root) or not 0 < local.stat().st_size <= 2*1024*1024:
        raise ValueError('Title page outside capture bounds')
    data = local.read_bytes()
    if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Title-page fingerprint differs')
    return data


def stylesheets(data):
    return re.findall(r'<link\s+href="([^"]+)"\s+rel="stylesheet"',data.decode('utf-8-sig'))


def controller_identity(data, identifier):
    # Unlike B_05, B_08 has no titleId variable. Its generated progression
    # URLs carry the internal identity. Never execute those purchase URLs.
    source = data.decode('utf-8-sig')
    identities = {value.upper() for value in re.findall(r'titleId=([A-Fa-f0-9]{16})(?=&|[\x27\x22])',source)}
    if identities != {identifier}:
        raise ValueError('Captured controller request/internal identity differs')
    tree = page_tree(data)
    title = tree.find('TitleName1stline')
    text = ''.join(child for node in title.walk() for child in node.children if isinstance(child,str)) if title else ''
    if title is None or not text.strip() or '\ufffd' in text:
        raise ValueError('Controller title missing or undecodable')
    return tree


class CapturedTitlePages:
    def __init__(self, capture, metadata, support_root, title_ids, index_path=None):
        self.capture = capture
        self.metadata = metadata
        self.support_root = Path(support_root).resolve()
        original, digest = read_manifest(capture.root)
        if digest != capture.manifest_sha256:
            raise ValueError('Title pages differ from shared capture manifest')
        support, self.support_manifest_sha256 = read_manifest(self.support_root)
        self.detail_rows, self.controller_rows = {}, {}
        self.excluded_details, self.excluded_controllers = {}, {}
        self.controller_mode_script = None
        self.detail_stylesheets = ['/oss/oss/common/css/oss.css','/oss/oss/common/css/error.css','/oss/oss/common/css/B_05.css']
        self.controller_stylesheets = self.detail_stylesheets[:2]
        self.controller_caption = 'Controller Confirmation'
        index = None
        if index_path is not None:
            index_path = Path(index_path)
            if index_path.stat().st_size > 2*1024*1024:
                raise ValueError('Oversized title-page index')
            raw_index = index_path.read_bytes()
            index = json.loads(raw_index)
            if (index.get('validation_revision') != INDEX_REVISION
                    or index.get('source') != SOURCE or index.get('archive_sha1') != ARCHIVE_SHA1
                    or index.get('capture_manifest_sha256') != digest
                    or index.get('metadata_sha256') != metadata.digest
                    or index.get('support_manifest_sha256') != self.support_manifest_sha256):
                raise ValueError('Title-page index source binding differs')
            for key in ('details','controllers'):
                if (not isinstance(index.get(key),dict) or not set(index[key]) <= title_ids
                        or len(index[key]) > 1000
                        or any(not re.fullmatch('[0-9a-f]{64}',value) for value in index[key].values())):
                    raise ValueError('Title-page index mapping differs')
            self.excluded_details = index.get('excluded_details',{})
            self.excluded_controllers = index.get('excluded_controllers',{})
            self.index_sha256 = hashlib.sha256(raw_index).hexdigest()
        else:
            self.index_sha256 = None
        total = 0
        for document,root,kind in ((original,capture.root,'detail'),(support,self.support_root,'controller')):
            seen = set()
            for row in document['files']:
                base,_,query = row['member'].rsplit('/',1)[-1].partition('?')
                fields = parse_qs(query)
                identifier = fields.get('titleId',[''])[0].upper()
                if (base != ('B_05.jsp' if kind=='detail' else 'B_08.jsp')
                        or fields.get('country') != ['JP'] or identifier not in title_ids):
                    continue
                if not row['member'].startswith('oss-auth.shop.wii.com/oss/serv/') or identifier in seen:
                    raise ValueError('Unexpected or ambiguous title-page member')
                seen.add(identifier)
                expected = metadata.get(identifier)
                if kind=='detail' and (expected is None or row['sha256'] != expected['capture_sha256']):
                    continue
                if index is not None:
                    accepted = index['details' if kind=='detail' else 'controllers']
                    if accepted.get(identifier) == row['sha256']:
                        (self.detail_rows if kind=='detail' else self.controller_rows)[identifier] = row
                    continue
                data = read_page(root,row)
                total += len(data)
                if total > 128*1024*1024:
                    raise ValueError('Title-page selection exceeds bounds')
                if kind=='detail':
                    if parse_detail(data,identifier) != expected:
                        raise ValueError('Captured detail metadata differs')
                    tree = page_tree(data)
                else:
                    try:
                        tree = controller_identity(data,identifier)
                    except ValueError as error:
                        self.excluded_controllers[identifier] = str(error)
                        continue
                    source = data.decode('utf-8-sig')
                    if '.innerHTML = "Controller Confirmation"' not in source:
                        raise ValueError('Unreviewed controller caption')
                    if row['sha256'] == CONTROLLER_REFERENCE_SHA256:
                        start = source.index('if(shop.isCompatibleMode){')
                        end = source.index('\n\n\tif (ecSupportsSession())',start)
                        self.controller_mode_script = ('function applyControllerMode(){\n'+source[start:end]+'\n}\n').encode()
                if stylesheets(data) != (self.detail_stylesheets if kind=='detail' else self.controller_stylesheets):
                    raise ValueError('Unreviewed title-page stylesheet set')
                if not re.search(r'setUnderButtonL\(true,\s*"Back"',data.decode('utf-8-sig')):
                    raise ValueError('Unreviewed title-page back caption')
                missing = self.missing_resources(tree,kind)
                if missing:
                    target = self.excluded_details if kind=='detail' else self.excluded_controllers
                    target[identifier] = sorted(missing)
                    continue
                (self.detail_rows if kind=='detail' else self.controller_rows)[identifier] = row
        if index is not None:
            if (set(self.detail_rows) != set(index['details'])
                    or set(self.controller_rows) != set(index['controllers'])):
                raise ValueError('Indexed title pages are absent from source manifests')
            reference = next((row for row in support['files'] if row['sha256']==CONTROLLER_REFERENCE_SHA256),None)
            if reference:
                source = read_page(self.support_root,reference).decode('utf-8-sig')
                start = source.index('if(shop.isCompatibleMode){')
                end = source.index('\n\n\tif (ecSupportsSession())',start)
                self.controller_mode_script = ('function applyControllerMode(){\n'+source[start:end]+'\n}\n').encode()
        if self.controller_mode_script is None:
            raise ValueError('Missing reviewed controller compatibility handler')

    def missing_resources(self, tree, kind):
        missing = set()
        for node in tree.walk():
            if node.tag not in ('img','input') or 'src' not in node.attrs:
                continue
            path = posixpath.normpath(node.attrs['src'])
            if kind=='detail' and path.startswith('/oss/ccs/'):
                continue
            if path not in self.capture.shared:
                missing.add(path)
        return missing

    @lru_cache(maxsize=16)
    def _page(self, identifier, kind):
        rows = self.detail_rows if kind=='detail' else self.controller_rows
        row = rows.get(identifier)
        if row is None:
            return None
        root = self.capture.root if kind=='detail' else self.support_root
        data = read_page(root,row)
        if kind=='detail':
            if parse_detail(data,identifier) != self.metadata.get(identifier):
                raise ValueError('Captured detail fields changed')
            tree = page_tree(data)
        else:
            tree = controller_identity(data,identifier)
        inline_styles = '\n'.join(re.findall(r'<style[^>]*>(.*?)</style>',data.decode('utf-8-sig'),re.I|re.S))
        return tree,inline_styles

    def page(self, identifier, kind='detail'):
        if kind not in ('detail','controller'):
            raise ValueError('Unknown title-page kind')
        return deepcopy(self._page(identifier,kind))

    def asset(self, path):
        if path == CONTROLLER_SCRIPT_URL:
            return 200,'text/javascript; charset=UTF-8',self.controller_mode_script
        return 404,'text/plain',b'Controller script not found'
