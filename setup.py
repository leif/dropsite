#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
from setuptools.command.install import install
import os

def readme():
    with open("README.md") as f:
        return f.read()

setup(
    name="dropsite",
    setup_requires=['setuptools'],
    install_requires = ['setuptools', "setuptools-git",
                        'werkzeug', 'subprocess', 'click', 'flask'
                        ],
    version="20180223.1",
    use_scm_version=True,
    author="Leif Ryge",
    author_email="leif@synthesize.us",
    description="Easy file transfer",
    long_description=readme(),
    license="none",
    keywords="python http onion tor filetransfer",
    url="https://github.com/INSERTURL",
    packages=["dropsite"],
    data_files=[(
                       "usr/share/applications/", 
                       [
                           "dropsite.desktop"
                       ],
                       "usr/share/icons/Adwaita/scalable/apps/", 
                       [
                           "dropsite.svg"
                       ],
                       "usr/share/icons/Adwaita/48x48/apps/", 
                       [
                           "dropsite.png"
                       ],
                       "usr/share/icons/", 
                       [
                           "dropsite.png"
                       ],
                       "usr/bin/", 
                       [
                           "dropsite.py",
                           "dropsite-wrapper.sh",
                           "dropsite-wrapper.sh",
                       ],

    )],
    python_requires=">=3.5",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        ],
    include_package_data=True,
    zip_safe=False,
    )
