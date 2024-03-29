from __future__ import annotations

import re
from asyncio import create_subprocess_exec, gather
from asyncio.subprocess import PIPE
from collections import ChainMap, defaultdict
from collections.abc import AsyncGenerator, Iterable
from contextlib import AsyncExitStack
from pathlib import Path
from typing import NamedTuple

import lxml.html
from aiohttp import ClientSession
from pkg_resources import resource_filename

from .types import LongVersion, ShortVersion
from .util import terminating


class OpenmodelicaPythonImage(NamedTuple):
    base: str
    ubuntu: str
    openmodelica: str
    python: LongVersion

    @property
    def tag(self) -> str:
        openmodelica = LongVersion.parse(self.openmodelica)
        return f"v{openmodelica}-python{self.python.as_short()}"

    def __str__(self) -> str:
        return f"{self.base}:{self.tag}"

    async def pull(self) -> None:
        process = await create_subprocess_exec("docker", "pull", f"{self}")
        async with terminating(process):
            await process.wait()

    async def build(self) -> None:
        dockerfile = Path(resource_filename(__name__, "Dockerfile")).resolve()

        async with AsyncExitStack() as stack:
            process = await stack.enter_async_context(
                terminating(
                    await create_subprocess_exec(
                        "docker",
                        "build",
                        f"{dockerfile.parent}",
                        f"--tag={self}",
                        f"--build-arg=BUILD_IMAGE={self.ubuntu}",
                        f"--build-arg=OPENMODELICA_IMAGE={self.openmodelica}",
                        f"--build-arg=PYTHON_VERSION={self.python}",
                    )
                )
            )

            assert await process.wait() == 0

    async def push(self) -> None:
        process = await create_subprocess_exec("docker", "push", f"{self}")
        async with terminating(process):
            assert await process.wait() == 0


async def search_python_versions(
    shorts: Iterable[ShortVersion],
    source_uri: str = "https://www.python.org/downloads/source/",
) -> list[LongVersion]:
    longs = defaultdict[ShortVersion, list[LongVersion]](list)
    async for long in _iter_python_version(source_uri):
        longs[long.as_short()].append(long)
    return [max(longs[short]) for short in sorted(longs.keys() & set(shorts))]


async def _iter_python_version(
    source_uri: str = "https://www.python.org/downloads/source/",
) -> AsyncGenerator[LongVersion, None]:
    pattern = re.compile(
        r"https?://www\.python\.org/ftp/python/\d+\.\d+\.\d+/"
        r"Python\-(\d+\.\d+\.\d+).tgz",
    )

    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(ClientSession())
        response = await stack.enter_async_context(session.get(source_uri))

        tree = lxml.html.fromstring(await response.text())

        for href in tree.xpath("//a/@href"):
            if (matched := pattern.match(href)) is not None:
                for group in matched.groups():
                    yield LongVersion.parse(group)


async def categorize_by_ubuntu_release(
    images: Iterable[str],
) -> dict[str, list[str]]:
    ubuntu_images = ChainMap[str, str](
        *await gather(*map(_get_ubuntu_image, images))
    )
    result = defaultdict[str, list[str]](list)
    for image, ubuntu in ubuntu_images.items():
        result[ubuntu].append(image)

    return dict(result)


async def _get_ubuntu_image(image: str) -> dict[str, str]:
    async with terminating(
        await create_subprocess_exec(
            "docker",
            "run",
            image,
            "cat",
            "/etc/lsb-release",
            stdout=PIPE,
        )
    ) as process:
        stdout, _ = await process.communicate()

        if (
            matched := re.search(
                r"DISTRIB_RELEASE=(\d+\.\d+)", stdout.decode("utf-8")
            )
        ) is not None:
            release = matched.group(1)
            return {image: f"ubuntu:{release}"}

    raise ValueError(image)
