from __future__ import annotations

import enum
import re
from asyncio import subprocess
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping, MutableSequence, Sequence
from functools import total_ordering
from importlib.resources import as_file, files
from typing import NewType, Self

from pydantic import BaseModel, ConfigDict

_URI = NewType("_URI", str)
_TargetName = NewType("_TargetName", str)

OPENMODELICA_URI = _URI("https://github.com/OpenModelica/OpenModelica.git")
PYTHON_URI = _URI("https://github.com/python/cpython.git")


async def categorize_version(
    uri: _URI,
) -> dict[tuple[int, int], set[tuple[int, int, int]]]:
    result = defaultdict[tuple[int, int], set[tuple[int, int, int]]](lambda: set())
    async for v in _iter_tags_in_remote(uri):
        result[v[:2]].add(v)
    return dict(sorted(result.items()))


async def _iter_tags_in_remote(uri: _URI) -> AsyncIterator[tuple[int, int, int]]:
    process = await subprocess.create_subprocess_exec(
        "git", "ls-remote", "--tags", uri, stdout=subprocess.PIPE
    )
    if process.stdout is None:
        raise RuntimeError
    async for buffer in process.stdout:
        for matched in re.finditer(
            rb"^[a-z0-9]{40}\s+\S+v?(?P<version>\d+\.\d+\.\d+)$", buffer
        ):
            major, minor, patch = map(int, matched.group("version").split(b"."))
            yield major, minor, patch


class DockerBake(BaseModel):
    model_config = ConfigDict(extra="allow")

    class _Target(BaseModel):
        model_config = ConfigDict(extra="allow")

        tags: MutableSequence[str]

    target: Mapping[str, _Target]

    async def build(self, indent: int | None) -> int:
        with as_file(files(__name__)) as package_directory:
            (package_directory / "docker-bake.json").write_text(
                self.model_dump_json(indent=indent), encoding="utf-8"
            )

            process = await subprocess.create_subprocess_exec(
                "docker", "buildx", "bake", cwd=package_directory
            )
            return await process.wait()

    @classmethod
    def from_targets(cls, targets: Sequence[Target]) -> Self:
        return cls.model_validate(
            {
                "group": {"default": {"targets": [x.name for x in targets]}},
                "target": {
                    x.name: {
                        "context": ".",
                        "dockerfile": "Dockerfile",
                        "args": x.args,
                        "tags": [
                            # "myapp:ubuntu", "myapp:latest"
                        ],
                    }
                    for x in targets
                },
            }
        )


@total_ordering
class Target(BaseModel):
    openmodelica: tuple[int, int, int]
    python: tuple[int, int, int]

    @property
    def name(self) -> _TargetName:
        return _TargetName(
            "{}-{}".format(
                "_".join(map(str, self.openmodelica)),
                "_".join(map(str, self.python)),
            )
        )

    @property
    def args(self) -> dict[str, str]:
        OM_MAJOR, OM_MINOR, OM_PATCH = map(str, self.openmodelica)
        PY_MAJOR, PY_MINOR, PY_PATCH = map(str, self.python)
        return dict(
            OM_MAJOR=OM_MAJOR,
            OM_MINOR=OM_MINOR,
            OM_PATCH=OM_PATCH,
            PY_MAJOR=PY_MAJOR,
            PY_MINOR=PY_MINOR,
            PY_PATCH=PY_PATCH,
        )

    def as_key(
        self, *, openmodelica: VersionFormat, python: VersionFormat
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        return (
            self.openmodelica[: openmodelica.value],
            self.python[: python.value],
        )

    def as_tag(
        self, *, repository: str, openmodelica: VersionFormat, python: VersionFormat
    ) -> str:
        _openmodelica, _python = self.as_key(openmodelica=openmodelica, python=python)
        return "{}:v{}-python{}".format(
            repository,
            ".".join(map(str, _openmodelica)),
            ".".join(map(str, _python)),
        )

    def __lt__(self, other: Self) -> bool:
        return self.openmodelica < other.openmodelica and self.python < other.python


@enum.unique
class VersionFormat(enum.Enum):
    short = 2
    long = 3


SHORT = VersionFormat.short
LONG = VersionFormat.long
