from __future__ import annotations

from typing import IO, Self

import tomllib
from PySide6.QtWidgets import QMainWindow, QWidget

from omcpyimage.config import Config
from omcpyimage.ui.mainwindow import Ui_MainWindow


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.__config = None

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)  # type: ignore[no-untyped-call]

    __config: Config | None

    @property
    def config(self) -> Config | None:
        return self.__config

    def setConfig(self, config: Config | IO[bytes]) -> Self:
        if not isinstance(config, Config):
            return self.setConfig(Config.model_validate(tomllib.load(config)))

        self.__config = config

        return self

    async def main(self) -> None:
        pass
