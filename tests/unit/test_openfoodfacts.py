from unittest.mock import MagicMock

from app._types import FetcherStatus
from app.openfoodfacts import TaxonomyPreprocessor
from app.taxonomy import Taxonomy, TaxonomyNodeResult


class TestTaxonomyPreprocessor:
    def test_preprocess_brands(self):
        # TaxonomyPreprocessor does not user the IndexConfig, so we can
        # provide a mock
        preprocessor = TaxonomyPreprocessor(MagicMock())
        brand_taxonomy = Taxonomy.from_dict(
            "brands",
            {
                "xx:flora": {
                    "name": {"xx": "Flora"},
                    "synonyms": {"xx": ["Flora"]},
                },
                "xx:nat-vie": {
                    "name": {"xx": "NAT&vie"},
                    "synonyms": {"xx": ["NAT&vie", "NAT&vie veggie"]},
                },
            },
        )
        node = brand_taxonomy["xx:nat-vie"]
        assert node is not None
        result = preprocessor.preprocess(brand_taxonomy, node)
        assert isinstance(result, TaxonomyNodeResult)
        assert result.status is FetcherStatus.FOUND
        # Check that we renamed "xx" to "main"
        assert result.node.names["main"] == "NAT&vie"
        assert result.node.synonyms["main"] == ["NAT&vie", "NAT&vie veggie"]
