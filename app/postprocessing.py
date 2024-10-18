from elasticsearch_dsl.response import Response

from app._types import JSONType
from app.config import IndexConfig
from app.utils import load_class_object_from_string


class BaseResultProcessor:
    def __init__(self, config: IndexConfig) -> None:
        self.config = config

    def process(self, response: Response, projection: set[str] | None) -> JSONType:
        """Post process results to add some information,
        or transform results to flatten them
        """
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
        output["aggregations"] = response.aggregations.to_dict()
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


def process_taxonomy_completion_response(response: Response) -> JSONType:
    output = {"took": response.took, "timed_out": response.timed_out}
    options = []
    suggestion = response.suggest["taxonomy_suggest"][0]
    for option in suggestion.options:
        result = {
            "id": option._source["id"],
            "text": option.text,
            "taxonomy_name": option._source["taxonomy_name"],
        }
        options.append(result)
    output["options"] = options
    return output
