class QueryAnalysisError(Exception):
    """Exception while building a query."""


class InvalidLuceneQueryError(QueryAnalysisError):
    """Invalid query, can't be analyzed by luqum"""


class FreeWildCardError(QueryAnalysisError):
    """You can't use '*' alone without specifying a search field"""


class UnknownFieldError(QueryAnalysisError):
    """An unknown field name was used in the query"""


class UnknownScriptError(QueryAnalysisError):
    """An unknown script name was used in the query"""


class QueryCheckError(QueryAnalysisError):
    """Encountered errors while checking Query"""

    def __init__(self, *args, errors: list[str]):
        super().__init__(*args)
        self.errors = errors

    def __str__(self):
        errors = "\n - " + "\n - ".join(self.errors)
        return f"{', '.join(self.args)}: {errors}"

    def __repr__(self):
        return (
            f"{self.__class__.__name__}({', '.join(self.args)}, errors={self.errors})"
        )
