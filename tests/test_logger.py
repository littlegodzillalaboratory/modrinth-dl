# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,duplicate-code,too-many-locals
import logging
import unittest

from modrinth_dl.logger import init


class TestLogger(unittest.TestCase):

    def test_init(self):
        logger = init()
        assert isinstance(logger, logging.LoggerAdapter) is True

    def test_init_returns_cached_logger(self):
        assert init() is init()
