#!/usr/bin/env python3
# coding: utf-8

import hashlib
import json
import logging
import os
import pickle
import shutil
import threading
import time
import traceback

from joker.diskcache import utils

logger = logging.getLogger(__name__)


class IntegrityError(ValueError):
    pass


def gen_tmp_affix():
    tup = os.getpid(), threading.get_ident(), time.time()
    return '_{}_{}_{}.tmp'.format(*tup)


class Tmpfile(object):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass

    def __init__(self, *paths):
        dirpath = os.path.join(*paths)
        self.path = os.path.join(dirpath, gen_tmp_affix())
        os.makedirs(dirpath, exist_ok=True)


class SimpleDiskCache(object):
    def __init__(self, dirpath, prefixlen=4):
        os.makedirs(dirpath, exist_ok=True)
        self.dirpath = dirpath
        self.prefixlen = prefixlen

    def get_path(self, key):
        return utils.proper_path(self.dirpath, key, self.prefixlen)

    def get_tmp_path(self, key):
        return self.get_path(key) + gen_tmp_affix()

    def load(self, key):
        path = self.get_path(key)
        if not os.path.exists(path):
            return
        logger.debug('use cached: ' + path)
        try:
            content = open(path, 'rb').read()
            hb = content[-16:]
            content = content[:-16]
            if hashlib.md5(content).digest() == hb:
                return content
            logger.debug('md5 hash mismatch')
        except IOError:
            traceback.print_exc()

    def save(self, key, content):
        path = self.get_path(key)
        logger.debug('save to cache: ' + path)
        hb = hashlib.md5(content).digest()
        tmp_path = self.get_tmp_path(key)
        with open(tmp_path, 'wb') as fout:
            fout.write(content)
            fout.write(hb)
        shutil.move(tmp_path, path)


class ContentAddressedStorage(object):
    chunksize = 16384

    def __init__(self, dirpath, algo='sha1', prefixlen=4):
        os.makedirs(dirpath, exist_ok=True)
        self.algo = algo
        self.dirpath = os.path.abspath(dirpath)
        self.prefixlen = prefixlen

    def get_path(self, key):
        return utils.standard_path(self.dirpath, key, self.prefixlen)

    def integrity_check(self, key, chunks):
        ho = hashlib.new(self.algo)
        for chunk in chunks:
            ho.update(chunk)
        return ho.hexdigest() == key

    def delete(self, key):
        path = self.get_path(key)
        if os.path.isfile(path):
            os.remove(path)

    def load(self, key):
        path = self.get_path(key)
        if not os.path.isfile(path):
            return
        with open(path, 'rb') as fin:
            chunk = fin.read(self.chunksize)
            while chunk:
                yield chunk
                chunk = fin.read(self.chunksize)

    def save(self, chunks):
        ho = hashlib.new(self.algo)
        with Tmpfile(self.dirpath, 'tmp') as tmpf:
            with open(tmpf.path, 'wb') as fout:
                for chunk in chunks:
                    ho.update(chunk)
                    fout.write(chunk)
            key = ho.hexdigest()
            path = self.get_path(key)
            # ignore duplicating content file
            if not os.path.exists(path):
                shutil.move(tmpf.path, path)
        return key


class DiskCache(object):
    def __init__(self, dirpath, algo='sha1', prefixlen=4):
        self.cas = ContentAddressedStorage(dirpath, algo, prefixlen)

    def get_path(self, key):
        cas = self.cas
        return utils.proper_path(cas.dirpath, key, cas.prefixlen)

    def delete(self, key):
        cas = self.cas
        meta_path = self.get_path(key)
        if not os.path.isfile(meta_path):
            logger.debug('not a file: %s', meta_path)
            return
        meta = json.load(open(meta_path))
        os.remove(meta_path)
        cas.delete(meta['cas_key'])

    def _load(self, key, check):
        cas = self.cas
        meta_path = self.get_path(key)
        if not os.path.isfile(meta_path):
            logger.debug('not a file: %s', meta_path)
            return
        meta = json.load(open(meta_path))
        cas_key = meta['cas_key']
        content = bytes().join(cas.load(cas_key))
        if check and not cas.integrity_check(cas_key, [content]):
            raise IntegrityError('checksum mismatch: ' + key)
        return meta, utils.decompress(content, meta['compression'])

    def load(self, key, check=False):
        meta_and_content = self._load(key, check)
        if meta_and_content:
            return meta_and_content[1]

    def pop(self, key, check=False):
        rv = self.load(key, check=check)
        self.delete(key)
        return rv

    def _save(self, key, meta, content, compression):
        content, compression = utils.compress(content, compression)
        cas_key = self.cas.save([content])
        meta.update({"cas_key": cas_key, "compression": compression})
        path = self.get_path(key)
        with open(path, 'w') as fout:
            json.dump(meta, fout)

    def save(self, key, content, compression=None):
        """
        :param key: (str)
        :param content: (bytes)
        :param compression: None or 'gzip'
        """
        self._save(key, {}, content, compression)


# TODO: pickle or marshal?
class PickledDiskCache(DiskCache):
    def save(self, key, obj, compression=None):
        if obj is None:
            return
        content = pickle.dumps(obj)
        self._save(key, {}, content, compression)

    def load(self, key, check=False):
        content = DiskCache.load(self, key, check)
        if content:
            return pickle.loads(content)
