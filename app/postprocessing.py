from app.config import Config, FieldType
from app.types import JSONType
from app.utils import load_class_object_from_string


class BaseResultProcessor:
    def __init__(self, config: Config) -> None:
        self.config = config

    def process(self, result: JSONType) -> JSONType:
        for field in self.config.fields:
            if field.name not in result:
                continue

            if field.type is FieldType.text_lang:
                lang_values = result.pop(field.name)
                for lang, text in lang_values.items():
                    suffix = "" if lang == "main" else f"_{lang}"
                    result[f"{field.name}{suffix}"] = text
            elif field.type is FieldType.taxonomy:
                result[field.name] = result.pop(field.name)["original"]

        return self.process_after(result)

    def process_after(self, result: JSONType) -> JSONType:
        """Subclass this method to post-process documents."""
        return result


def load_result_processor(config: Config) -> BaseResultProcessor | None:
    result_processor_cls = (
        load_class_object_from_string(config.result_processor)
        if config.result_processor
        else BaseResultProcessor
    )
    return result_processor_cls(config)
