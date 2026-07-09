"""C-extension build script for the native capability-module fixture (#884)."""

from setuptools import Extension, setup

setup(ext_modules=[Extension("native_ext", sources=["native_ext.c"])])
