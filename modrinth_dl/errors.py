"""Errors raised by Modrinth Downloader."""


class ModrinthDlError(Exception):
    """Raised when a Modrinth project cannot be resolved or downloaded.

    Covers this library's own checks: no compatible version, no suitable
    file, and checksum mismatch. Network, HTTP, and Modrinth API client
    errors, e.g. an unknown project slug, are not wrapped and propagate
    as-is.
    """
