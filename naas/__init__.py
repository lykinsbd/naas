#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
Initialization module for NAAS. Sets version
"""

from importlib.metadata import version

__version__ = version("naas")
__base_response__ = {"app": "naas", "version": __version__}
