# Runtime Technical Debt Tracking

This file tracks technical-debt markers introduced in runtime paths.

- SAL-TECHDEBT-001: Compute translated facet values when facet is taxonomy-backed.
  Files: app/facets.py
- SAL-TECHDEBT-002: Localize built-in pseudo facet labels (e.g. Other/None).
  Files: app/facets.py
- SAL-TECHDEBT-003: Compute selected state for synthetic facet entries.
  Files: app/facets.py
- SAL-TECHDEBT-004: Support translated facet display names.
  Files: app/facets.py
- SAL-TECHDEBT-005: Evaluate scatter charts against full result set (or dedicated aggregation), not current page only.
  Files: app/charts.py
- SAL-TECHDEBT-006: Align parser UnknownFilter handling with UnknownOperation strategy.
  Files: app/query.py
- SAL-TECHDEBT-007: Upstream SIMPLE_EXPR_FIELDS allowances to luqum.
  Files: app/query_transformers.py
- SAL-TECHDEBT-008: Move dotted field-name support into luqum core.
  Files: app/query_transformers.py
- SAL-TECHDEBT-009: Upstream phrase/open-range checks into LuceneCheck.
  Files: app/query_transformers.py
- SAL-TECHDEBT-010: Validate configured sub-fields once sub-field support is implemented.
  Files: app/query_transformers.py
- SAL-TECHDEBT-011: Support suggestion rendering by taxonomy/type.
  Files: frontend/src/search-suggester.ts
- SAL-TECHDEBT-012: Add fallback field-level query condition when no facet matches a taxonomy suggestion.
  Files: frontend/src/search-suggester.ts
