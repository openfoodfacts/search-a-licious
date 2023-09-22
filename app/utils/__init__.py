import importlib

from .log import get_logger


def load_class_object_from_string(qualifier: str) -> type:
    module_name, cls_name = qualifier.rsplit(".", maxsplit=1)
    return getattr(importlib.import_module(module_name), cls_name)
