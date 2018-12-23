# === Start Python 2/3 compatibility
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614
# === End Python 2/3 compatibility

from os import path
from setuptools import setup, find_packages

import py3port

here = path.abspath(path.dirname(__file__))


# Get the long description from the README file
with open(path.join(here, 'README.rst'), 'r', encoding='utf-8') as f:
    long_description = f.read()

with open(path.join(here, 'requirements.txt'), 'r') as f:
    requirements = f.readlines()

setup(
    name='py3port',
    version=py3port.__version__,
    license='MIT',
    author="Richard Shaw",
    description="Tools for porting code to Python 3",
    long_description=long_description,
    url="http://github.com/jrs65/py3port/",

    packages=find_packages(),

    install_requires=requirements,

    entry_points="""
        [console_scripts]
        py3port=py3port.main:main
    """
)
