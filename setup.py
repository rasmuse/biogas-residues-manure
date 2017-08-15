# -*- coding: utf-8 -*-

import os
from os import path
from setuptools import setup, find_packages
from pip.req import parse_requirements
from pip.download import PipSession

# install_reqs = parse_requirements('requirements.txt', session=PipSession())
# reqs = [str(ir.req) for ir in install_reqs]

PACKAGE_NAME = 'biogasrm'

setup(
    name='biogasrm',
    version='0.1.1',
    url='',
    license='GPLv3',
    author='Rasmus Einarsson',
    author_email=(
        'rasmus [dot] einarsson [at] chalmers [dot] se'),
    description=(
        'Estimate of the biogas potential from crop residues '
        'and manure in EU28.'),
    # install_requires=reqs,
    packages=['biogasrm'],
    package_dir={'biogasrm': 'biogasrm'},
    entry_points='''
        [console_scripts]
        biogasrm-prep=biogasrm.prep_data:cli
        biogasrm-sample=biogasrm.sample:cli
        biogasrm-substrates=biogasrm.substrates:cli
    ''',
    extras_require = {
        },
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4'
    ]
    )
