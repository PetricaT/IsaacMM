from pathlib import Path
import logging
import sys

logger = logging.getLogger(name=__name__)


class platform:
    _instance: None = None

    def __new__(cls, *args, **kwargs):
        sentinel = "_PLATFORM_SINGLETON"
        existing = globals().get(sentinel)
        if existing is not None and isinstance(existing, cls):
            return existing

        inst = super().__new__(cls)
        inst.__dict__.update({"_initialized": False, "config": {}, "config_file": None})
        globals()[sentinel] = inst
        return inst

    def __init__(self) -> None:
        self.PLATFORM: str = sys.platform

    def config_directory(self) -> Path:
        match self.PLATFORM:
            case "win32":
                config_directory = Path.home() / "AppData" / "Local" / "IsaacMM"
                pass
            case "darwin":
                config_directory = (
                    Path.home() / "Library" / "Application Support" / "IsaacMM"
                )
                pass
            case "linux":
                config_directory = Path.home() / ".config" / "IsaacMM"
                pass
            case _:
                logging.error(f"\033[31m OS Not Supported \033[41m'{sys.platform}'")
                sys.exit(1)

        return config_directory
