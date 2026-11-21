"""Checksum helpers for verifying files downloaded from Modrinth."""

import hashlib
from typing import Any, Optional, Tuple

# Listed in order of preference. Modrinth publishes sha1 and sha512 for each
# file; sha1 is preferred because it is cheaper, and the check only guards
# against corrupt or truncated downloads (they already arrive over HTTPS).
SUPPORTED_ALGORITHMS = ("sha1", "sha512", "sha256")
CHUNK_SIZE = 8192


def get_expected_hash(file_info: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return the expected checksum of a Modrinth file.

    :param file_info: Modrinth file metadata, with a ``hashes`` attribute.
        The API client gives an object with one attribute per algorithm,
        while raw Modrinth API JSON gives a dict, so both are accepted.
    :return: Tuple of (algorithm, value), or (None, None) when Modrinth
        publishes no supported checksum for the file.
    """
    hashes = getattr(file_info, "hashes", None)
    if not hashes:
        return None, None

    if isinstance(hashes, dict):
        hash_map = hashes
    else:
        hash_map = {
            algorithm: getattr(hashes, algorithm, None)
            for algorithm in SUPPORTED_ALGORITHMS
        }

    for algorithm in SUPPORTED_ALGORITHMS:
        hash_value = hash_map.get(algorithm)
        if hash_value:
            return algorithm, hash_value

    return None, None


def calculate_file_hash(file_path: str, algorithm: str) -> str:
    """Calculate the checksum of a local file.

    :param file_path: Path of the file to hash.
    :param algorithm: Hash algorithm name, e.g. ``sha1``.
    :return: Hex digest of the file content.
    """
    hasher = hashlib.new(algorithm)
    with open(file_path, "rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
