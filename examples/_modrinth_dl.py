# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,duplicate-code,too-many-locals
from modrinth_dl import Downloader

downloader = Downloader(delay_in_seconds=1)

downloader.download_mods(
    ["lithium", "ferrite-core"], "fabric", "1.21.4", "../stage/test-examples/mods"
)
downloader.download_datapacks(
    ["terralith"], "1.21.4", "../stage/test-examples/world/datapacks"
)
