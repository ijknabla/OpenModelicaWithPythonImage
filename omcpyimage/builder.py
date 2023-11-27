import re
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack
from pathlib import Path

import lxml.html
from aiohttp import ClientSession
from pkg_resources import resource_filename

from .types import LongVersion, ShortVersion
from .util import terminating


async def pull(image: str) -> None:
    process = await create_subprocess_exec("docker", "pull", image)
    async with terminating(process):
        assert await process.wait() == 0


async def build(image: str, python: LongVersion) -> str:
    openmodelica = LongVersion.parse(image)
    dockerfile = Path(resource_filename(__name__, "Dockerfile")).resolve()

    tag = f"ijknabla/openmodelica:v{openmodelica}-python{python.as_short()}"
    ubuntu = await ubuntu_version(image)

    async with AsyncExitStack() as stack:
        process = await stack.enter_async_context(
            terminating(
                await create_subprocess_exec(
                    "docker",
                    "build",
                    f"{dockerfile.parent}",
                    f"--tag={tag}",
                    f"--build-arg=BUILD_IMAGE={ubuntu}",
                    f"--build-arg=OPENMODELICA_IMAGE={image}",
                    f"--build-arg=PYTHON_VERSION={python}",
                )
            )
        )

        assert await process.wait() == 0

    return tag


async def ubuntu_version(image: str) -> str:
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
            return f"ubuntu:{release}"

    raise ValueError(image)


async def search_python_version(
    short: ShortVersion,
    source_uri: str = "https://www.python.org/downloads/source/",
) -> AsyncGenerator[LongVersion, None]:
    pattern = re.compile(
        r"https?://www\.python\.org/ftp/python/"
        rf"{re.escape(str(short))}\.\d+/"
        rf"Python\-({re.escape(str(short))}\.\d+).tgz",
    )

    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(ClientSession())
        response = await stack.enter_async_context(session.get(source_uri))

        tree = lxml.html.fromstring(await response.text())

        for href in tree.xpath("//a/@href"):
            if (matched := pattern.match(href)) is not None:
                for group in matched.groups():
                    yield LongVersion.parse(group)
