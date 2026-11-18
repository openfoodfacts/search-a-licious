# How to upgrade from 1.4.0

This page lists what changed, for a client of the API or a user of the Open Food Facts configuration,
between version 1.4.0 and the code that follows it.

It was written by comparing the OpenAPI documents that the code of both versions generates,
and the two `data/config/openfoodfacts.yml` files.
It only states what is different: it does not say how to stay compatible.
Other changes (fixes, new features of the web components...) are in the [changelog](https://github.com/openfoodfacts/search-a-licious/blob/main/CHANGELOG.md).

## Rebuild the index

The fields of the Open Food Facts index changed (see [below](#fields-of-the-open-food-facts-index)).
An index created by 1.4.0 does not have the new ones (for example `last_updated_t`, `selected_images`),
which the configuration now declares.

Import the taxonomies and then the data again,
see [how to update the index](./how-to-update-index.md) and the [tutorial](./tutorial.md#initial-import).
A full import creates a new index and switches the alias to it at the end.

## `/autocomplete`

* `lang` was replaced by `langs`, a comma-separated list (`langs=fr,en`).
  A request that still sends `lang` is **not an error**: the parameter is ignored and the results are in English, the default.
* `q` must not be empty (the answer is a 422).
* The names given in `taxonomy_names` are now plural, see [the list below](#taxonomy-names).
  An unknown name is not an error either, it gives an empty answer.

## `/search`

* `page_size` must be at least 1.
* In the body of `POST /search`, the `chart_type` of a chart is `DistributionChart` or `ScatterChart`,
  instead of `DistributionChartType` and `ScatterChartType`.
* The `debug` part of the response no longer has a `query`.
  It is empty by default, and the new `debug_info` parameter asks for what it contains:
  `es_query` (the Elasticsearch query, what `debug.query` was), `lucene_query` and `aggregations`.
* New optional parameters: `boost_phrase` (default `false`), `charts_y_axis` (default `false`) and `debug_info`.
* The errors of the response now have a `status`.

## Fields of the Open Food Facts index

The configuration declares 92 fields, it was 46.
A query on a field that does not exist is refused, so queries have to use the new names.
For example, `categories_tags:"en:milks"` becomes `categories:"en:milks"`.

These fields have a new name:

| 1.4.0 | Now |
|---|---|
| `allergens_tags` | `allergens` |
| `brands_tags` | `brands` |
| `categories_tags` | `categories` |
| `countries_tags` | `countries` |
| `labels_tags` | `labels` |
| `origins_tags` | `origins` |
| `traces_tags` | `traces` |

The new fields read the same key of the product (`input_field` in the configuration).
For instance `categories` is made from `categories_tags` of the product.

These fields of 1.4.0 are not in the configuration any more, so they are not indexed:
`abbreviated_product_name`, `ecoscore_data`, `ecoscore_grade`, `ecoscore_score`, `images` and `nova_groups`.
Images are in `selected_images` and `uploaded_images`,
and the `environmental_score` fields are indexed.

## Taxonomy names

The names of the taxonomies are the ones of the `taxonomy` section of the configuration.
They are what `/autocomplete` expects in `taxonomy_names`.

| 1.4.0 | Now |
|---|---|
| `category` | `categories` |
| `label` | `labels` |
| `additive` | `additives` |
| `allergen` | `allergens` |
| `amino_acid` | `amino_acids` |
| `brand` | `brands` |
| `country` | `countries` |
| `food_group` | `food_groups` |
| `improvement` | `improvements` |
| `ingredient` | `ingredients` |
| `language` | `languages` |
| `mineral` | `minerals` |
| `nova_group` | `nova_groups` |
| `nucleotide` | `nucleotides` |
| `nutrient` | `nutrients` |
| `origin` | `origins` |
| `other_nutritional_substance` | `other_nutritional_substances` |
| `packaging_material` | `packaging_materials` |
| `packaging_shape` | `packaging_shapes` |
| `state` | `states` |
| `vitamin` | `vitamins` |

These did not change: `data_quality`, `ingredients_analysis`, `ingredients_processing`, `misc`, `packaging_recycling`, `periods_after_opening` and `preservation`.
`stores` is new.
