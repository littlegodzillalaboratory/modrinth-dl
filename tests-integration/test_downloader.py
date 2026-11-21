# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,duplicate-code,too-many-locals
import os
import shutil
import tempfile
import unittest

from modrinth_dl import Downloader, ModrinthDlError

MINECRAFT_VERSION = "1.21.4"


class TestDownloader(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)
        self.downloader = Downloader(delay_in_seconds=1)

    def test_download_mods_then_skip_on_second_run(self):
        mods_dir = os.path.join(self.temp_dir, "mods")

        changed = self.downloader.download_mods(
            ["ferrite-core"], "fabric", MINECRAFT_VERSION, mods_dir
        )
        self.assertTrue(changed)
        files = os.listdir(mods_dir)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].endswith(".jar"))

        changed = self.downloader.download_mods(
            ["ferrite-core"], "fabric", MINECRAFT_VERSION, mods_dir
        )
        self.assertFalse(changed)

    def test_download_datapacks(self):
        datapacks_dir = os.path.join(self.temp_dir, "world", "datapacks")

        changed = self.downloader.download_datapacks(
            ["terralith"], MINECRAFT_VERSION, datapacks_dir
        )
        self.assertTrue(changed)
        files = os.listdir(datapacks_dir)
        self.assertEqual(len(files), 1)
        self.assertTrue(files[0].lower().endswith(".zip"))

    def test_download_mod_with_unknown_game_version_raises_error(self):
        with self.assertRaises(ModrinthDlError):
            self.downloader.download_mod(
                "ferrite-core", "fabric", "0.0.0", self.temp_dir
            )
