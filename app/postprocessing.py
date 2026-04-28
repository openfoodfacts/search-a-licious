from app._types import JSONType
from app.config import IndexConfig
from app.utils import load_class_object_from_string


class BaseResultProcessor:
    def __init__(self, config: IndexConfig) -> None:
        self.config = config

    def process(self, response: dict, projection: set[str] | None) -> JSONType:
        """Post process results to add some information,
        or transform results to flatten them
        """
        output = {
            "took": response["took"],
            "timed_out": response["timed_out"],
            "count": response["hits"]["total"]["value"],
            "is_count_exact": response["hits"]["total"]["relation"] == "eq",
        }
        hits = []
        for hit in response["hits"]["hits"]:
            result = hit["_source"]
            result["_score"] = hit.get("_score")

            # TODO make it an unsplit option or move to specific off post processing
            for fname in self.config.text_lang_fields:
                if fname not in result:
                    continue
                # Flatten the language dict
                lang_values = result.pop(fname)
                for lang, text in lang_values.items():
                    # FIXME: this reproduces OFF behaviour, but is this a good thing?
                    suffix = "" if lang == "main" else f"_{lang}"
                    result[f"{fname}{suffix}"] = text

            result = self.process_after(result)
            if projection:
                result = dict((k, v) for k, v in result.items() if k in projection)
            hits.append(result)
        output["hits"] = hits
        output["aggregations"] = response.get("aggregations", {})
        return output

    def process_after(self, result: JSONType) -> JSONType:
        """Subclass this method to post-process documents."""
        return result


def load_result_processor(config: IndexConfig) -> BaseResultProcessor | None:
    """Load the result processor class from the config.

    :param config: the index configuration to use
    :return: the initialized result processor
    """
    result_processor_cls = (
        load_class_object_from_string(config.result_processor)
        if config.result_processor is not None
        else BaseResultProcessor
    )
    return result_processor_cls(config)


def process_taxonomy_completion_response(
    response: dict, input: str, langs: list[str]
) -> JSONType:
    output = {"took": response["took"], "timed_out": response["timed_out"]}
    options = []
    ids = set()
    lang = langs[0]
    for suggestion_id, suggestions in response.get("suggest", {}).items():
        if not suggestion_id.startswith("taxonomy_suggest_"):
            continue
        for suggestion in suggestions:
            for option in suggestion.get("options", []):
                if option["_source"]["id"] in ids:
                    continue
                ids.add(option["_source"]["id"])
                result = {
                    "id": option["_source"]["id"],
                    "text": option["text"],
                    "name": option["_source"]["name"].get(lang, ""),
                    "score": option["_score"],
                    "input": input,
                    "taxonomy_name": option["_source"]["taxonomy_name"],
                }
                options.append(result)
    # highest score first
    output["options"] = sorted(
        options, key=lambda option: option["score"], reverse=True
    )
    return output
