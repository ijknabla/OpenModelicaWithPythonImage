from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from subprocess import run

import click


@click.command()
@click.option(
    "-C",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.argument(
    "ui",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def main(c: Path, ui: Sequence[Path]) -> None:
    src_and_dst = [
        (src, (c / f"{src.name.lower()}").with_suffix(".py")) for src in ui
    ]

    for src, dst in src_and_dst:
        run(["pyside6-uic", f"--output={dst}", f"{src}"], check=True)


if __name__ == "__main__":
    main()
