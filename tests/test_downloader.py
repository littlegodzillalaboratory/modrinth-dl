# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,duplicate-code,too-many-locals,too-many-public-methods
import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, mock_open, patch

from modrinth_dl.downloader import Downloader
from modrinth_dl.errors import ModrinthDlError

CONTENT = b"some file content"
CONTENT_SHA1 = hashlib.sha1(CONTENT, usedforsecurity=False).hexdigest()
DEST_DIR = "/opt/fabricmc/workspace/mods"


def make_file(filename, primary=True, sha1=CONTENT_SHA1):
    hashes = SimpleNamespace(sha1=sha1, sha512=None) if sha1 else None
    return SimpleNamespace(
        filename=filename,
        primary=primary,
        url=f"https://cdn.modrinth.com/{filename}",
        hashes=hashes,
    )


def make_version(files, loaders=("fabric",), game_versions=("1.21.4",)):
    return SimpleNamespace(
        files=list(files),
        loaders=list(loaders) if loaders is not None else None,
        game_versions=list(game_versions) if game_versions is not None else None,
    )


class DownloaderTestCase(unittest.TestCase):
    """Base test case that patches every external dependency of downloader."""

    def setUp(self):
        patchers = {
            "init": patch("modrinth_dl.downloader.init"),
            "requests": patch("modrinth_dl.downloader.requests"),
            "time": patch("modrinth_dl.downloader.time"),
            "exists": patch("modrinth_dl.downloader.os.path.exists"),
            "makedirs": patch("modrinth_dl.downloader.os.makedirs"),
            "remove": patch("modrinth_dl.downloader.os.remove"),
            "calculate_file_hash": patch("modrinth_dl.downloader.calculate_file_hash"),
            "open": patch(
                "modrinth_dl.downloader.open", new_callable=mock_open, create=True
            ),
        }
        self.mocks = {}
        for name, patcher in patchers.items():
            self.mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)

        self.logger = MagicMock()
        self.mocks["init"].return_value = self.logger
        self.mocks["exists"].return_value = False

        self.response = MagicMock()
        self.response.iter_content.return_value = [CONTENT[:5], b"", CONTENT[5:]]
        self.mocks["requests"].get.return_value = self.response

        self.client = MagicMock()
        self.downloader = Downloader(client=self.client, delay_in_seconds=2)


class TestConstructor(unittest.TestCase):

    @patch("modrinth_dl.downloader.init")
    @patch("modrinth_dl.downloader.Client")
    def test_creates_client_when_not_given(self, func_client, func_init):
        downloader = Downloader()
        self.assertIs(downloader.client, func_client.return_value)
        self.assertEqual(downloader.delay_in_seconds, 0)
        self.assertIs(downloader.logger, func_init.return_value)

    @patch("modrinth_dl.downloader.init")
    @patch("modrinth_dl.downloader.Client")
    def test_uses_given_client(self, func_client, _func_init):
        client = MagicMock()
        downloader = Downloader(client=client, delay_in_seconds=5)
        self.assertIs(downloader.client, client)
        self.assertEqual(downloader.delay_in_seconds, 5)
        func_client.assert_not_called()


class TestDownloadMod(DownloaderTestCase):

    def test_downloads_latest_compatible_version(self):
        self.client.list_project_versions.return_value = [
            make_version([make_file("lithium-forge.jar")], loaders=["forge"]),
            make_version([make_file("lithium-old-mc.jar")], game_versions=["1.20"]),
            make_version([make_file("lithium-no-meta.jar")], loaders=None),
            make_version([make_file("lithium-new.jar")]),
            make_version([make_file("lithium-old.jar")]),
        ]

        result = self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)

        self.assertTrue(result)
        self.client.list_project_versions.assert_called_once_with("lithium")
        self.mocks["requests"].get.assert_called_once_with(
            "https://cdn.modrinth.com/lithium-new.jar", stream=True, timeout=60
        )
        self.response.raise_for_status.assert_called_once()
        self.mocks["makedirs"].assert_called_once_with(DEST_DIR, exist_ok=True)
        self.mocks["open"].assert_called_once_with(f"{DEST_DIR}/lithium-new.jar", "wb")
        handle = self.mocks["open"]()
        handle.write.assert_has_calls([call(CONTENT[:5]), call(CONTENT[5:])])
        self.assertEqual(handle.write.call_count, 2)

    def test_prefers_primary_file(self):
        self.client.list_project_versions.return_value = [
            make_version(
                [
                    make_file("lithium-sources.jar", primary=False),
                    make_file("lithium.jar", primary=True),
                ]
            ),
        ]

        self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)

        self.mocks["open"].assert_called_once_with(f"{DEST_DIR}/lithium.jar", "wb")

    def test_falls_back_to_first_file_without_primary(self):
        self.client.list_project_versions.return_value = [
            make_version(
                [
                    make_file("lithium-a.jar", primary=False),
                    make_file("lithium-b.jar", primary=False),
                ]
            ),
        ]

        self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)

        self.mocks["open"].assert_called_once_with(f"{DEST_DIR}/lithium-a.jar", "wb")

    def test_no_compatible_version_raises_error(self):
        self.client.list_project_versions.return_value = [
            make_version([make_file("lithium.jar")], game_versions=["1.20"]),
        ]

        with self.assertRaisesRegex(
            ModrinthDlError,
            "No compatible version found for 'lithium' with Minecraft 1.21.4 "
            "and loader fabric",
        ):
            self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)

    def test_no_files_raises_error(self):
        self.client.list_project_versions.return_value = [make_version([])]

        with self.assertRaisesRegex(
            ModrinthDlError, "No downloadable file found for mod 'lithium'"
        ):
            self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)


class TestDownloadDatapack(DownloaderTestCase):

    def test_downloads_primary_zip(self):
        self.client.list_project_versions.return_value = [
            make_version(
                [make_file("terralith.jar", primary=False), make_file("Terralith.ZIP")],
                loaders=["datapack"],
            ),
        ]

        result = self.downloader.download_datapack("terralith", "1.21.4", DEST_DIR)

        self.assertTrue(result)
        self.mocks["open"].assert_called_once_with(f"{DEST_DIR}/Terralith.ZIP", "wb")

    def test_ignores_loader(self):
        self.client.list_project_versions.return_value = [
            make_version([make_file("terralith.zip")], loaders=None),
        ]

        self.assertTrue(
            self.downloader.download_datapack("terralith", "1.21.4", DEST_DIR)
        )

    def test_falls_back_to_first_zip_when_primary_is_not_zip(self):
        self.client.list_project_versions.return_value = [
            make_version(
                [
                    make_file("terralith.jar", primary=True),
                    make_file("terralith.zip", primary=False),
                ]
            ),
        ]

        self.downloader.download_datapack("terralith", "1.21.4", DEST_DIR)

        self.mocks["open"].assert_called_once_with(f"{DEST_DIR}/terralith.zip", "wb")

    def test_skips_version_without_game_versions(self):
        self.client.list_project_versions.return_value = [
            make_version([make_file("terralith-unknown.zip")], game_versions=None),
            make_version([make_file("terralith.zip")]),
        ]

        self.downloader.download_datapack("terralith", "1.21.4", DEST_DIR)

        self.mocks["open"].assert_called_once_with(f"{DEST_DIR}/terralith.zip", "wb")

    def test_no_zip_file_raises_error(self):
        self.client.list_project_versions.return_value = [
            make_version([make_file("terralith.jar")]),
        ]

        with self.assertRaisesRegex(
            ModrinthDlError, "No downloadable zip file found for datapack 'terralith'"
        ):
            self.downloader.download_datapack("terralith", "1.21.4", DEST_DIR)

    def test_no_compatible_version_raises_error(self):
        self.client.list_project_versions.return_value = [
            make_version([make_file("terralith.zip")], game_versions=["1.20"]),
        ]

        with self.assertRaisesRegex(
            ModrinthDlError,
            "No compatible version found for 'terralith' with Minecraft 1.21.4",
        ):
            self.downloader.download_datapack("terralith", "1.21.4", DEST_DIR)


class TestDownloadFile(DownloaderTestCase):

    def setUp(self):
        super().setUp()
        self.client.list_project_versions.return_value = [
            make_version([make_file("lithium.jar")]),
        ]

    def test_existing_file_with_valid_checksum_is_skipped(self):
        self.mocks["exists"].return_value = True
        self.mocks["calculate_file_hash"].return_value = CONTENT_SHA1

        result = self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)

        self.assertFalse(result)
        self.mocks["calculate_file_hash"].assert_called_once_with(
            f"{DEST_DIR}/lithium.jar", "sha1"
        )
        self.mocks["requests"].get.assert_not_called()
        self.mocks["remove"].assert_not_called()

    def test_existing_file_with_checksum_mismatch_is_redownloaded(self):
        self.mocks["exists"].return_value = True
        self.mocks["calculate_file_hash"].return_value = "stale-checksum"

        result = self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)

        self.assertTrue(result)
        self.mocks["remove"].assert_called_once_with(f"{DEST_DIR}/lithium.jar")
        self.mocks["requests"].get.assert_called_once()
        self.logger.warning.assert_called_once()

    def test_existing_file_without_published_checksum_is_skipped(self):
        self.client.list_project_versions.return_value = [
            make_version([make_file("lithium.jar", sha1=None)]),
        ]
        self.mocks["exists"].return_value = True

        result = self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)

        self.assertFalse(result)
        self.mocks["calculate_file_hash"].assert_not_called()
        self.mocks["requests"].get.assert_not_called()

    def test_download_without_published_checksum_is_not_verified(self):
        self.client.list_project_versions.return_value = [
            make_version([make_file("lithium.jar", sha1=None)]),
        ]

        result = self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)

        self.assertTrue(result)
        self.mocks["remove"].assert_not_called()

    def test_download_with_checksum_mismatch_is_removed_and_raises_error(self):
        self.client.list_project_versions.return_value = [
            make_version([make_file("lithium.jar", sha1="expected-checksum")]),
        ]

        with self.assertRaisesRegex(
            ModrinthDlError,
            "Checksum mismatch for 'lithium' file 'lithium.jar': "
            f"expected sha1=expected-checksum, got {CONTENT_SHA1}",
        ):
            self.downloader.download_mod("lithium", "fabric", "1.21.4", DEST_DIR)

        self.mocks["remove"].assert_called_once_with(f"{DEST_DIR}/lithium.jar")


class TestDownloadAll(DownloaderTestCase):

    def test_download_mods_reports_changed_when_any_downloaded(self):
        with patch.object(
            self.downloader, "download_mod", side_effect=[False, True, False]
        ) as func_download_mod:
            result = self.downloader.download_mods(
                ["sodium", "lithium", "ferrite-core"], "fabric", "1.21.4", DEST_DIR
            )

        self.assertTrue(result)
        func_download_mod.assert_has_calls(
            [
                call("sodium", "fabric", "1.21.4", DEST_DIR),
                call("lithium", "fabric", "1.21.4", DEST_DIR),
                call("ferrite-core", "fabric", "1.21.4", DEST_DIR),
            ]
        )
        self.mocks["time"].sleep.assert_has_calls([call(2), call(2), call(2)])

    def test_download_mods_reports_unchanged_when_none_downloaded(self):
        with patch.object(self.downloader, "download_mod", return_value=False):
            result = self.downloader.download_mods(
                ["sodium"], "fabric", "1.21.4", DEST_DIR
            )

        self.assertFalse(result)

    def test_download_mods_with_empty_list(self):
        result = self.downloader.download_mods([], "fabric", "1.21.4", DEST_DIR)

        self.assertFalse(result)
        self.mocks["time"].sleep.assert_not_called()

    def test_download_datapacks_reports_changed_when_any_downloaded(self):
        with patch.object(
            self.downloader, "download_datapack", side_effect=[True, False]
        ) as func_download_datapack:
            result = self.downloader.download_datapacks(
                ["terralith", "incendium"], "1.21.4", DEST_DIR
            )

        self.assertTrue(result)
        func_download_datapack.assert_has_calls(
            [
                call("terralith", "1.21.4", DEST_DIR),
                call("incendium", "1.21.4", DEST_DIR),
            ]
        )
        self.assertEqual(self.mocks["time"].sleep.call_count, 2)
