from elasticsearch_dsl.response import Response

from app._types import JSONType
from app.config import Config, FieldType
from app.utils import load_class_object_from_string


class BaseResultProcessor:
    def __init__(self, config: Config) -> None:
        self.config = config

    def process(self, response: Response, projection: set[str] | None) -> JSONType:
        output = {
            "took": response.took,
            "timed_out": response.timed_out,
            "count": response.hits.total["value"],
            "is_count_exact": response.hits.total["relation"] == "eq",
        }
        hits = []
        for hit in response.hits:
            result = hit.to_dict()
            result["_score"] = hit.meta.score

            for field in self.config.fields.values():
                if field.name not in result:
                    continue

                if field.type is FieldType.text_lang:
                    lang_values = result.pop(field.name)
                    for lang, text in lang_values.items():
                        suffix = "" if lang == "main" else f"_{lang}"
                        result[f"{field.name}{suffix}"] = text
                elif field.type is FieldType.taxonomy:
                    result[field.name] = result.pop(field.name)["original"]

            result = self.process_after(result)
            if projection:
                result = dict((k, v) for k, v in result.items() if k in projection)
            hits.append(result)
        output["hits"] = hits
        output["aggregations"] = response.aggregations.to_dict()
        return output

    def process_after(self, result: JSONType) -> JSONType:
        """Subclass this method to post-process documents."""
        return result


def load_result_processor(result_processor: str | None) -> BaseResultProcessor | None:
    result_processor_cls = (
        load_class_object_from_string(result_processor)
        if result_processor is not None
        else BaseResultProcessor
    )
    return result_processor_cls(result_processor)


class CompletionProcessor(BaseResultProcessor):
    def process(self, response: Response) -> JSONType:
        output = {"took": response.took, "timed_out": response.timed_out}
        options = []
        suggestion = response.suggest["taxonomy_suggest"][0]
        for option in suggestion.options:
            result = {
                "id": option._source["id"],
                "text": option.text,
            }
            options.append(result)
        output["options"] = options
        return output
