#!/usr/bin/env python3
# coding: utf-8

import os
import re

import setuptools

# CAUTION:
# Do NOT import your package from your setup.py

_nsp = 'joker'
_pkg = 'diskcache'
_names = [_nsp, _pkg]
_names = [s for s in _names if s]


def read(filename):
    with open(filename) as f:
        return f.read()


def version_find():
    names = _names + ['__init__.py']
    path = os.path.join(*names)
    root = os.path.dirname(__file__)
    path = os.path.join(root, path)
    regex = re.compile(
        r'''^__version__\s*=\s*('|"|'{3}|"{3})([.\w]+)\1\s*(#|$)''')
    with open(path) as fin:
        for line in fin:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            mat = regex.match(line)
            if mat:
                return mat.groups()[1]
    raise ValueError('__version__ definition not found')


config = {
    'name': '-'.join(_names),
    'version': version_find(),
    'description': 'Primitive disk-backed cache, probably useful in web scraping',
    'keywords': '',
    'url': 'https://github.com/frozflame/joker-diskcache',
    'author': 'anonym',
    'author_email': 'anonym@example.com',
    'license': "GNU General Public License (GPL)",
    'packages': setuptools.find_namespace_packages(include=['joker.*']),
    'zip_safe': False,
    'install_requires': read("requirements.txt"),
    'classifiers': [
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    # ensure copy static file to runtime directory
    'include_package_data': True,
    'long_description': read('README.md'),
    'long_description_content_type': "text/markdown",
}

if _nsp:
    config['namespace_packages'] = [_nsp]


setuptools.setup(**config)


