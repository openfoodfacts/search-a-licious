from app._import import BaseDocumentFetcher
from app.indexing import BaseDocumentPreprocessor
from app.postprocessing import BaseResultProcessor


class TestDocumentFetcher(BaseDocumentFetcher):
    pass


class TestDocumentPreprocessor(BaseDocumentPreprocessor):
    pass


class TestResultProcessor(BaseResultProcessor):
    pass
