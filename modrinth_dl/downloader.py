"""Download Minecraft mods and datapacks from Modrinth.

For each project, the newest version matching the Minecraft version (and
loader, for mods) is resolved through the Modrinth API, then one file from
that version is downloaded and verified against its published checksum.
"""

import hashlib
import os
import time
from typing import Callable, List, Optional

from modrinth_api_wrapper import Client
from modrinth_api_wrapper.models import File, Version
import requests

from .checksum import CHUNK_SIZE, calculate_file_hash, get_expected_hash
from .errors import ModrinthDlError
from .logger import init

# requests applies this to connecting and to each wait between received bytes,
# not to the whole download, so a large file on a slow link can take longer.
DOWNLOAD_TIMEOUT_IN_SECONDS = 60
DATAPACK_FILE_EXTENSION = ".zip"


class Downloader:
    """Downloads the latest compatible files of Modrinth projects.

    Download methods return whether anything was downloaded, so callers
    such as Ansible modules can report ``changed``. Files from older
    versions of a project already in the destination directory are left in
    place; removing them is the caller's responsibility.
    """

    def __init__(self, client: Optional[Client] = None, delay_in_seconds: int = 0):
        """Initialise downloader.

        Args:
            client: Modrinth API client, a new Client is created when omitted.
            delay_in_seconds: Seconds to wait after each project when
                downloading a list of projects, to go easy on Modrinth's API.
        """
        self.client = client if client is not None else Client()
        self.delay_in_seconds = delay_in_seconds
        self.logger = init()

    def download_mods(
        self, slugs: List[str], loader: str, game_version: str, dest_dir: str
    ) -> bool:
        """Download the latest compatible version of each mod.

        :param slugs: Modrinth project slugs, e.g. ``lithium``.
        :param loader: Mod loader, e.g. ``fabric``.
        :param game_version: Minecraft version, e.g. ``1.21.4``.
        :param dest_dir: Directory to save the mod files to.
        :return: True if any mod was downloaded.
        :raises ModrinthDlError: On the first mod that fails. Mods processed
            before it stay downloaded and later mods are not attempted.
        """
        self.logger.info(
            "%s mod(s) to download for Minecraft %s and loader %s",
            len(slugs),
            game_version,
            loader,
        )
        return self._download_all(
            slugs,
            lambda slug: self.download_mod(slug, loader, game_version, dest_dir),
        )

    def download_datapacks(
        self, slugs: List[str], game_version: str, dest_dir: str
    ) -> bool:
        """Download the latest compatible version of each datapack.

        :param slugs: Modrinth project slugs, e.g. ``terralith``.
        :param game_version: Minecraft version, e.g. ``1.21.4``.
        :param dest_dir: Directory to save the datapack files to.
        :return: True if any datapack was downloaded.
        :raises ModrinthDlError: On the first datapack that fails. Datapacks
            processed before it stay downloaded and later ones are not
            attempted.
        """
        self.logger.info(
            "%s datapack(s) to download for Minecraft %s",
            len(slugs),
            game_version,
        )
        return self._download_all(
            slugs,
            lambda slug: self.download_datapack(slug, game_version, dest_dir),
        )

    def download_mod(
        self, slug: str, loader: str, game_version: str, dest_dir: str
    ) -> bool:
        """Download the latest version of a mod compatible with a loader.

        :param slug: Modrinth project slug.
        :param loader: Mod loader, e.g. ``fabric``.
        :param game_version: Minecraft version.
        :param dest_dir: Directory to save the mod file to.
        :return: True if the mod was downloaded, False if already present.
        :raises ModrinthDlError: If no compatible version or file exists.
        """
        # The API client models loaders and game_versions as optional, so a
        # version without them is treated as incompatible rather than failing.
        version = self._find_latest_version(
            slug,
            lambda version: loader in (version.loaders or [])
            and game_version in (version.game_versions or []),
            f"Minecraft {game_version} and loader {loader}",
        )
        # Any file type is accepted for mods; the primary file is preferred.
        primary_file = _select_file(version.files, lambda file: True)
        if primary_file is None:
            raise ModrinthDlError(f"No downloadable file found for mod '{slug}'")
        return self._download_file(slug, primary_file, dest_dir)

    def download_datapack(self, slug: str, game_version: str, dest_dir: str) -> bool:
        """Download the latest version of a datapack.

        :param slug: Modrinth project slug.
        :param game_version: Minecraft version.
        :param dest_dir: Directory to save the datapack file to.
        :return: True if the datapack was downloaded, False if already
            present.
        :raises ModrinthDlError: If no compatible version or zip file exists.
        """
        # Loaders are not checked: datapacks are loaded by Minecraft itself.
        # Only the version that is newest overall is considered, so a project
        # whose latest release is a mod build without a zip raises an error
        # even when an older version has one.
        version = self._find_latest_version(
            slug,
            lambda version: game_version in (version.game_versions or []),
            f"Minecraft {game_version}",
        )
        # Datapack projects often also ship a mod build as a .jar, but only a
        # .zip can be placed in a world's datapacks directory.
        zip_file = _select_file(
            version.files,
            lambda file: file.filename.lower().endswith(DATAPACK_FILE_EXTENSION),
        )
        if zip_file is None:
            raise ModrinthDlError(
                f"No downloadable zip file found for datapack '{slug}'"
            )
        return self._download_file(slug, zip_file, dest_dir)

    def _download_all(self, slugs: List[str], download: Callable) -> bool:
        """Download each project in turn, pausing after each one.

        The pause also follows skipped projects and the last project, which
        keeps API request spacing predictable at the cost of a final wait.
        """
        changed = False
        for slug in slugs:
            if download(slug):
                changed = True
            time.sleep(self.delay_in_seconds)
        return changed

    def _find_latest_version(
        self, slug: str, is_compatible: Callable, target: str
    ) -> Version:
        """Return the newest project version that passes a compatibility check.

        Relies on Modrinth listing project versions newest first, so the
        first match is the latest. Beta and alpha versions are not filtered
        out and win if they are newest.
        """
        self.logger.debug("Fetching project versions for '%s'...", slug)
        versions = self.client.list_project_versions(slug)
        for version in versions:
            if is_compatible(version):
                return version
        raise ModrinthDlError(f"No compatible version found for '{slug}' with {target}")

    def _download_file(self, slug: str, file_info: File, dest_dir: str) -> bool:
        """Download a Modrinth file unless a verified copy already exists.

        An existing file with a matching checksum is kept, and one with a
        different checksum is replaced. When Modrinth publishes no supported
        checksum, an existing file is trusted by its name alone, and the
        download is not verified.

        :return: True if the file was downloaded, False if already present.
        :raises ModrinthDlError: If the downloaded file fails checksum check.
        """
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, file_info.filename)
        algorithm, expected_hash = get_expected_hash(file_info)

        if os.path.exists(dest_path):
            if not algorithm:
                self.logger.info(
                    "'%s' already exists at '%s', skipping download",
                    file_info.filename,
                    dest_path,
                )
                return False
            if calculate_file_hash(dest_path, algorithm) == expected_hash:
                self.logger.info(
                    "'%s' already exists at '%s' with valid checksum, "
                    "skipping download",
                    file_info.filename,
                    dest_path,
                )
                return False
            self.logger.warning(
                "'%s' exists at '%s' but checksum mismatch, re-downloading",
                file_info.filename,
                dest_path,
            )
            os.remove(dest_path)

        self.logger.info(
            "Downloading '%s' from %s...", file_info.filename, file_info.url
        )
        downloaded_hash = _write_response(file_info.url, dest_path, algorithm)

        if algorithm and downloaded_hash != expected_hash:
            os.remove(dest_path)
            raise ModrinthDlError(
                f"Checksum mismatch for '{slug}' file '{file_info.filename}': "
                f"expected {algorithm}={expected_hash}, got {downloaded_hash}"
            )

        self.logger.info(
            "Successfully downloaded '%s' to '%s'", file_info.filename, dest_path
        )
        return True


def _select_file(files: List[File], is_wanted: Callable) -> Optional[File]:
    """Return the primary file if wanted, otherwise the first wanted file."""
    for file in files:
        if file.primary and is_wanted(file):
            return file
    for file in files:
        if is_wanted(file):
            return file
    return None


def _write_response(
    url: str, dest_path: str, algorithm: Optional[str]
) -> Optional[str]:
    """Stream a URL to a file, hashing it on the way to avoid a second read.

    Content is written straight to ``dest_path``, not via a temporary file,
    so an interrupted download leaves a partial file behind. With a
    published checksum, the next run detects and replaces it.

    :return: Checksum of the content when an algorithm is set, else None.
    """
    response = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT_IN_SECONDS)
    response.raise_for_status()

    hasher = hashlib.new(algorithm) if algorithm else None
    with open(dest_path, "wb") as file_handle:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:  # keep-alive chunks carry no data
                continue
            file_handle.write(chunk)
            if hasher:
                hasher.update(chunk)

    return hasher.hexdigest() if hasher else None
