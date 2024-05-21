from __future__ import annotations

from typing import IO, Generic, TypeVar, cast, final

import tomllib
from PySide6.QtWidgets import QMainWindow, QWidget

from omcpyimage.config import Config
from omcpyimage.ui.mainwindow import Ui_MainWindow

ConfigType = TypeVar("ConfigType", Config, None)


@final
class MainWindow(QMainWindow, Generic[ConfigType]):
    def __init__(self: MainWindow[None], parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.__config = None

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)  # type: ignore[no-untyped-call]

    __config: ConfigType

    @property
    def config(self) -> ConfigType:
        return self.__config

    def setConfig(self, config: Config | IO[bytes]) -> MainWindow[Config]:
        if not isinstance(config, Config):
            return self.setConfig(Config.model_validate(tomllib.load(config)))

        _self = cast(MainWindow[Config], self)  # type: ignore[redundant-cast]
        _self.__config = config

        return _self

    async def main(self) -> None:
        pass
