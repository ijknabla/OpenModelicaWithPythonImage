import sys
from asyncio import gather, run
from collections import defaultdict
from functools import wraps
from itertools import chain

import click

from . import (
    LONG,
    OPENMODELICA_URI,
    PYTHON_URI,
    SHORT,
    DockerBake,
    Target,
    categorize_version,
)


@click.command()
@click.option("--repository", type=str, required=True)
@click.option("--indent", type=int)
@(lambda f: wraps(f)(lambda *args, **kwargs: run(f(*args, **kwargs))))
async def main(*, repository: str, indent: int | None) -> None:
    openmodelica, python = await gather(
        categorize_version(OPENMODELICA_URI),
        categorize_version(PYTHON_URI),
    )

    targets = [
        Target(
            openmodelica=max(openmodelica_long),
            python=max(python_long),
        )
        for openmodelica_short, openmodelica_long in openmodelica.items()
        if (1, 20) <= openmodelica_short
        for python_short, python_long in python.items()
        if (3, 9) <= python_short
    ]

    docker_bake = DockerBake.from_targets(targets)

    for openmodelica_format, python_format in [
        (SHORT, SHORT),
        (LONG, SHORT),
        (LONG, LONG),
    ]:
        category = defaultdict[str, list[Target]](lambda: [])
        for target in targets:
            category[
                target.as_tag(
                    repository=repository,
                    openmodelica=openmodelica_format,
                    python=python_format,
                )
            ].append(target)
        for tag, _targets in category.items():
            docker_bake.target[max(_targets).name].tags.append(tag)

    if returncode := await docker_bake.build(indent=indent):
        sys.exit(returncode)

    for tag in chain.from_iterable(x.tags for x in docker_bake.target.values()):
        print(tag, file=sys.stdout)


if __name__ == "__main__":
    main()
