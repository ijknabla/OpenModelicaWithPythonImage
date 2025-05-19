from __future__ import annotations

import enum
import re
import sys
from asyncio import subprocess
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping, MutableSequence, Sequence
from enum import Enum, auto, unique
from functools import partial, total_ordering
from importlib.resources import as_file, files
from typing import Any, Generic, NewType, Self, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

_print = partial(print, file=sys.stderr)

_URI = NewType("_URI", str)
_Ref = NewType("_Ref", str)
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


async def listup_tags_in_remote(uri: _URI) -> list[_Ref]:
    return [tag async for tag in _iter_tags_in_remote2(uri)]


async def _iter_tags_in_remote2(uri: _URI) -> AsyncIterator[_Ref]:
    process = await subprocess.create_subprocess_exec(
        "git", "ls-remote", "--tags", uri, stdout=subprocess.PIPE
    )
    if process.stdout is None:
        raise RuntimeError

    pattern = re.compile(rb"^[a-z0-9]{40}\s*refs/tags/(?P<version>\S*)\s*$")

    async for buffer in process.stdout:
        if (matched := pattern.match(buffer)) is None:
            message = f"{buffer=!r}"
            raise ValueError(message)
        yield _Ref(matched.group("version").decode(encoding="ascii"))


_SuffixType = TypeVar("_SuffixType")


@total_ordering
class SemVer(BaseModel, Generic[_SuffixType]):
    major: int
    minor: int
    patch: int
    suffix: _SuffixType

    @model_validator(mode="before")
    @classmethod
    def _parse_string(cls, obj: Any) -> Any:
        if not isinstance(obj, str):
            return obj

        pattern = re.compile(
            r"v?"
            r"(?P<major>\d+)\."
            r"(?P<minor>\d+)\."
            r"(?P<patch>\d+)"
            r"(?P<suffix>.*)"
        )

        if (matched := pattern.match(obj)) is None:
            message = f"{obj!r} does not matches pattern={pattern.pattern=!r}"
            raise ValueError(message)

        return {
            "major": matched.group("major"),
            "minor": matched.group("minor"),
            "patch": matched.group("patch"),
            "suffix": matched.group("suffix"),
        }

    @property
    def tuple(self) -> tuple[int, int, int, _SuffixType]:
        return self.major, self.minor, self.patch, self.suffix

    def __lt__(self, other: Self, /) -> bool:
        return self.tuple < other.tuple


@unique
class Dev(int, Enum):
    yes = auto()
    no = auto()


@unique
class Release(int, Enum):
    none = auto()
    alpha = auto()
    beta = auto()


@total_ordering
@unique
class InfType(Enum):
    this = auto()

    def __gt__(self, other: Any, /) -> bool:
        return not isinstance(other, InfType)


Inf = InfType.this


@total_ordering
class OpenModelicaSuffix(BaseModel):
    dev: Dev
    release: Release
    micro: int | InfType

    @model_validator(mode="before")
    @classmethod
    def _parse_string(cls, obj: Any) -> Any:
        if not isinstance(obj, str):
            return obj

        sep = r"[.-]"
        pattern = re.compile(
            rf"^({sep}?(?P<dev>dev))?({sep}?(?P<release>alpha|beta))?({sep}?(?P<micro>\d+))?$"
        )

        if (matched := pattern.match(obj)) is None:
            message = f"{obj!r} does not matches pattern={pattern.pattern!r}"
            raise ValueError(message)

        value = matched.group("dev")
        if value is None:
            dev = Dev.no
        else:
            dev = Dev.yes

        value = matched.group("release")
        if value is None:
            release = Release.none
        else:
            release = Release[value]

        micro: int | InfType
        value = matched.group("micro")
        if value is None:
            micro = Inf
        else:
            micro = int(value)

        return {
            "dev": dev,
            "release": release,
            "micro": micro,
        }

    @property
    def tuple(self) -> tuple[Dev, Release, int | InfType]:
        return self.dev, self.release, self.micro

    def __lt__(self, other: Self, /) -> bool:
        return self.tuple < other.tuple


PythonVersion = SemVer[str | None]
# OpenModelicaVersion = SemVer[OpenModelicaVersion | str]
OpenModelicaVersion = SemVer[OpenModelicaSuffix]


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
