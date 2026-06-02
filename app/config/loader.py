from pathlib import Path
from .models import Config
from .settings import settings

# _CONFIG is a global variable that contains the search-a-licious configuration
# used. It is specified by the envvar CONFIG_PATH.
# use get_config() to access it.
_CONFIG: Config | None = None


def get_config() -> Config:
    """Return the object containing global configuration

    It raises if configuration was not yet set
    """
    if _CONFIG is None:
        raise RuntimeError(
            "No configuration is configured, set envvar "
            "CONFIG_PATH with the path of the yaml configuration file"
        )
    return _CONFIG


def set_global_config(config_path: Path):
    global _CONFIG
    _CONFIG = Config.from_yaml(config_path)
    return _CONFIG


if settings.config_path:
    if not settings.config_path.is_file():
        raise RuntimeError(f"config file does not exist: {settings.config_path}")

    set_global_config(settings.config_path)
