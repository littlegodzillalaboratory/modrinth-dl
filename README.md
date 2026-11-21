<!-- BEGIN:AVATAR -->
![Avatar](avatar.jpg)
<!-- END:AVATAR -->

<!-- BEGIN:BADGES -->
[![Build Status](https://github.com/littlegodzillalaboratory/modrinth-dl/workflows/CI/badge.svg)](https://github.com/littlegodzillalaboratory/modrinth-dl/actions?query=workflow%3ACI)
[![Code Scanning Status](https://github.com/littlegodzillalaboratory/modrinth-dl/workflows/CodeQL/badge.svg)](https://github.com/littlegodzillalaboratory/modrinth-dl/actions?query=workflow%3ACodeQL)
[![Dependencies Status](https://img.shields.io/librariesio/release/pypi/modrinth-dl)](https://libraries.io/npm/modrinth-dl)
[![Security Status](https://snyk.io/test/github/littlegodzillalaboratory/modrinth-dl/badge.svg)](https://snyk.io/test/github/littlegodzillalaboratory/modrinth-dl)
[![Published Version](https://img.shields.io/pypi/v/modrinth-dl.svg)](https://pypi.python.org/pypi/modrinth-dl)
<!-- END:BADGES -->

# Modrinth Downloader

Modrinth Downloader is a Python lib for downloading Minecraft add-ons, such as mods and datapacks, from [Modrinth](https://modrinth.com).

For each Modrinth project, it downloads the newest version that supports the given Minecraft version (and mod loader, for mods). Files that already exist with a matching checksum are skipped, and every download is verified against the checksum published by Modrinth.

## Installation

```shell
pip3 install modrinth-dl
```

## Usage

Download mods for a Fabric server:

```python
from modrinth_dl import Downloader

downloader = Downloader(delay_in_seconds=2)

changed = downloader.download_mods(
    ["lithium", "ferrite-core"], "fabric", "1.21.4", "/opt/fabricmc/mods"
)
```

Download datapacks into a world:

```python
changed = downloader.download_datapacks(
    ["terralith"], "1.21.4", "/opt/fabricmc/world/datapacks"
)
```

Both return `True` when at least one file was downloaded, and `False` when every file was already present. A single project can also be downloaded with `download_mod` and `download_datapack`.

When a project has no version compatible with the given Minecraft version (or loader), or no suitable file, or a download fails its checksum check, a `modrinth_dl.ModrinthDlError` is raised.

## Configuration

These are the `Downloader` constructor arguments:

| Argument | Type | Description | Default |
|----------|------|-------------|---------|
| `client` | `modrinth_api_wrapper.Client` | Modrinth API client | A new `Client()` |
| `delay_in_seconds` | int | Seconds to wait after each project when downloading a list of projects, to go easy on Modrinth's API | 0 |

## Colophon

<!-- BEGIN:DEVELOPERS_GUIDE -->
[Developer's Guide](https://littlegodzillalaboratory.github.io/developers-guide-python.html)
<!-- END:DEVELOPERS_GUIDE -->

<!-- BEGIN:BUILD_REPORTS -->
Build reports:

* [Lint report](https://littlegodzillalaboratory.github.io/modrinth-dl/lint/pylint/index.html)
* [Code complexity report](https://littlegodzillalaboratory.github.io/modrinth-dl/complexity/radon/index.html)
* [Unit tests report](https://littlegodzillalaboratory.github.io/modrinth-dl/test/pytest/index.html)
* [Test coverage report](https://littlegodzillalaboratory.github.io/modrinth-dl/coverage/coverage/index.html)
* [Integration tests report](https://littlegodzillalaboratory.github.io/modrinth-dl/test-integration/pytest/index.html)
* [API Documentation](https://littlegodzillalaboratory.github.io/modrinth-dl/doc/sphinx/index.html)

<!-- END:BUILD_REPORTS -->
