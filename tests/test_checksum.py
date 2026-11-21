# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,duplicate-code,too-many-locals
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import mock_open, patch

from modrinth_dl.checksum import calculate_file_hash, get_expected_hash

FILE_CONTENT = b"some mod content"


class TestGetExpectedHash(unittest.TestCase):

    def test_hashes_object_prefers_sha1(self):
        file_info = SimpleNamespace(hashes=SimpleNamespace(sha1="abc", sha512="def"))
        self.assertEqual(get_expected_hash(file_info), ("sha1", "abc"))

    def test_hashes_object_falls_back_to_sha512(self):
        file_info = SimpleNamespace(hashes=SimpleNamespace(sha1=None, sha512="def"))
        self.assertEqual(get_expected_hash(file_info), ("sha512", "def"))

    def test_hashes_dict(self):
        file_info = SimpleNamespace(hashes={"sha256": "ghi"})
        self.assertEqual(get_expected_hash(file_info), ("sha256", "ghi"))

    def test_hashes_dict_with_unsupported_algorithm_only(self):
        file_info = SimpleNamespace(hashes={"md5": "jkl"})
        self.assertEqual(get_expected_hash(file_info), (None, None))

    def test_missing_hashes(self):
        file_info = SimpleNamespace()
        self.assertEqual(get_expected_hash(file_info), (None, None))

    def test_empty_hashes(self):
        file_info = SimpleNamespace(hashes={})
        self.assertEqual(get_expected_hash(file_info), (None, None))


class TestCalculateFileHash(unittest.TestCase):

    @patch(
        "modrinth_dl.checksum.open",
        new_callable=mock_open,
        read_data=FILE_CONTENT,
        create=True,
    )
    def test_sha1(self, func_open):
        result = calculate_file_hash("lithium.jar", "sha1")
        self.assertEqual(
            result, hashlib.sha1(FILE_CONTENT, usedforsecurity=False).hexdigest()
        )
        func_open.assert_called_once_with("lithium.jar", "rb")

    @patch(
        "modrinth_dl.checksum.open",
        new_callable=mock_open,
        read_data=FILE_CONTENT,
        create=True,
    )
    def test_sha512(self, func_open):  # pylint: disable=unused-argument
        result = calculate_file_hash("lithium.jar", "sha512")
        self.assertEqual(result, hashlib.sha512(FILE_CONTENT).hexdigest())
