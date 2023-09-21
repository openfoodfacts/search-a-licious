import abc

from app.config import Config
from app.types import JSONType
from app.utils import load_class_object_from_string


class BaseResultProcessor(abc.ABC):
    def __init__(self, config: Config) -> None:
        self.config = config

    @abc.abstractmethod
    def process_result(self, result: JSONType) -> JSONType:
        pass


def load_result_processor(config: Config) -> BaseResultProcessor | None:
    result_processor_cls = (
        load_class_object_from_string(config.result_processor)
        if config.result_processor
        else None
    )
    if result_processor_cls:
        return result_processor_cls(config)
    return None
