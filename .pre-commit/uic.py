from __future__ import annotations

import asyncio
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from collections.abc import Sequence


@click.command()
@click.option(
    "--input-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.argument(
    "ui", nargs=-1, type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@(lambda f: wraps(f)(lambda *args, **kwargs: asyncio.run(f(*args, **kwargs))))
async def main(input_dir: Path, output_dir: Path, ui: Sequence[Path]) -> None:
    await asyncio.gather(
        *(
            uic(ui=_ui, py=(output_dir / _ui.relative_to(input_dir)).with_suffix(".py"))
            for _ui in ui
        )
    )


async def uic(ui: Path, py: Path) -> None:
    pyside6_uic = await asyncio.create_subprocess_exec(
        "pyside6-uic", f"--output={py}", f"{ui}"
    )
    try:
        await pyside6_uic.wait()
    except Exception:
        pyside6_uic.terminate()


if __name__ == "__main__":
    main()
