import glob
import json
import os

from app._import import BaseDocumentFetcher
from app._types import FetcherResult, FetcherStatus, JSONType
from app.indexing import BaseDocumentPreprocessor
from app.openfoodfacts import TaxonomyPreprocessor
from app.postprocessing import BaseResultProcessor
from app.taxonomy import Taxonomy, TaxonomyNode, TaxonomyNodeResult


class CallRegistration:
    """A class to register calls

    Because search-a-licious may launch different process
    We need to register them in a persistent way
    """

    _fname = None

    @classmethod
    def register_call(cls, *args):
        if cls._fname is None:
            cls._fname = f"/tmp/{cls.__name__}-{os.getpid()}.jsonl"
        with open(cls._fname, "a") as f:
            f.write(json.dumps(args if len(args) > 1 else args[0]) + "\n")

    @classmethod
    def clean_calls(cls):
        for fpath in glob.glob(f"/tmp/{cls.__name__}-*.jsonl"):
            os.remove(fpath)

    @classmethod
    def get_calls(cls):
        # get all calls, that might have been made in other processes
        calls = [
            json.loads(line)
            for fpath in glob.glob(f"/tmp/{cls.__name__}-*.jsonl")
            for line in open(fpath)
            if line.strip()
        ]
        return calls


class TestTaxonomyPreprocessor(TaxonomyPreprocessor, CallRegistration):

    def preprocess(self, taxonomy: Taxonomy, node: TaxonomyNode) -> TaxonomyNodeResult:
        self.register_call((taxonomy.name, node.id))
        return super().preprocess(taxonomy, node)


class TestDocumentFetcher(BaseDocumentFetcher, CallRegistration):

    def fetch_document(self, stream_name: str, item: JSONType) -> FetcherResult:
        self.register_call(item)
        return FetcherResult(
            status=FetcherStatus.FOUND,
            document=item,
        )


class TestDocumentPreprocessor(BaseDocumentPreprocessor, CallRegistration):

    def preprocess(self, document: JSONType) -> FetcherResult:
        self.register_call(document)
        # FIXME if we could specify sub object field we would not need this
        # but for now we want tests to pass
        # ensure floats
        for key, value in list(document.get("nutriments", {}).items()):
            if value is not None:
                document["nutriments"][key] = float(value)
        return FetcherResult(
            status=FetcherStatus.FOUND,
            document=document,
        )


class TestResultProcessor(BaseResultProcessor, CallRegistration):

    def process_after(self, result: JSONType) -> JSONType:
        self.register_call(result)
        return result
