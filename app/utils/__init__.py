import importlib

from .log import get_logger, init_sentry  # noqa: F401


def load_class_object_from_string(qualifier: str) -> type:
    module_name, cls_name = qualifier.rsplit(".", maxsplit=1)
    return getattr(importlib.import_module(module_name), cls_name)
