from __future__ import annotations

from asyncio import Lock, TimeoutError, gather, wait_for
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from operator import itemgetter
from typing import IO

import click
import tomllib
from PySide6 import QtAsyncio
from PySide6.QtCore import QCoreApplication

from . import builder
from .builder import OpenmodelicaPythonImage
from .config import Config


@click.command
@click.argument(
    "config_io",
    metavar="CONFIG.TOML",
    type=click.File(mode="rb"),
)
@click.option("--limit", type=int, default=1)
def main(config_io: IO[bytes], limit: int) -> None:
    async def impl() -> None:
        config = Config.model_validate(tomllib.load(config_io))

        pythons = await builder.search_python_versions(config.python)

        ubuntu_openmodelica = await builder.categorize_by_ubuntu_release(config.from_)

        images = {
            OpenmodelicaPythonImage(
                base="ijknabla/openmodelica",
                ubuntu=ubuntu,
                openmodelica=openmodelica,
                python=python,
            )
            for ubuntu, openmodelicas in ubuntu_openmodelica.items()
            for openmodelica in openmodelicas
            for python in pythons
        }

        python0 = {image for image in images if image.python == pythons[0]}
        ubuntu0 = {
            image
            for image in images
            if image.openmodelica in map(itemgetter(0), ubuntu_openmodelica.values())
        }

        group0 = images & ubuntu0 & python0
        group1 = images & ubuntu0 - python0
        group2 = images - ubuntu0

        assert (group0 | group1 | group2) == images

        await gather(*(image.pull() for image in images), return_exceptions=True)
        for group in [group0, group1, group2]:
            await gather(*(image.build() for image in sorted(group)))
        await gather(*(image.push() for image in images))
        for image in sorted(images):
            print(image)

    QCoreApplication()
    QtAsyncio.run(impl(), keep_running=False)


@asynccontextmanager
async def lock_all(*locks: Lock) -> AsyncGenerator[None, None]:
    async with AsyncExitStack() as stack:
        while True:
            lock_all = gather(*(stack.enter_async_context(lock) for lock in locks))

            try:
                await wait_for(lock_all, 1e-3)
                break
            except TimeoutError:
                await stack.aclose()
                continue

        yield


if __name__ == "__main__":
    main()
