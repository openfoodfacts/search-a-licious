# Explain Query Language

The idea of Search-a-licious is to provide a powerfull yet easy to use API,
through the use of a well proven language: Lucene Query Language.

While Elasticsearch provides a way to use this language in the queries,
it has some important limitations like the lack of support for nested and object fields.

Thanks to the [luqum library](https://github.com/jurismarches/luqum),
Search-a-licious is able to use Lucene Query Language in a broader way.

Search-a-licious also use luqum to introspect the query
and transform it to add features corresponding to your configuration
and leverage taxonomies and other peculiarities.

It enables for example taking into account synonyms,
or adding the languages to query about on the fly
without the need to complexify the query to much at API level.

## Query syntax

The query syntax is quite simple, you can either:

* query for simple word in the default texts fields (those having `full_text_search` property in your configuration)
  by simply having the word in your query:
  ```
  chocolate
  ```
  Entries with text `chocolate`
* or match exactly a full sentences by using quotes:
  ```
  "dark chocolate"
  ```
  Entries with text `dark chocolate`
* you can also match a word or phrase in a specific field by using the field name, followed by a colon:
  ```
  labels:organic
  ```
  Entries with labels containing `organic`
* you can have more than one term, the query will try to match all terms:
  ```
  "dark chocolate" labels:organic
  ```
  Entries with text `dark chocolate` and labels containing `organic`
* you can combine queries with `AND`, `OR` and `NOT` operators, and use parenthesis to group them:
  ```
  "dark chocolate AND (labels:organic OR labels:vegan) AND NOT nutriscore:(e OR d)"
  ```
  Entries with text `dark chocolate`, labels containing `organic` or `vegan`, and Nutri-Score not `e` or `d`
* you can query a sub field by using "." or ":":
  ```
  nutrients.sugar_100g:[10 TO 15]
  ```
  equivalent to:
  ```
  nutrients:sugar_100g:[10 TO 15]
  ```
  Entries with sugar between 10 and 15 grams per 100g
* in range you can use * for unbounded values:
  ```
  nutrients.sugar_100g:[* TO 20] AND nutrients.proteins_100g:[2 TO *]
  ```
  Entries with sugar below 20 g and proteins above 2g for 100g
* match field existence with `*`:
  ```
  nutriscore:*
  ```
  Entries with Nutri-Score computed

## Different type of fields

When you created you configuration, you defined different fields types.
It's important because the matching possibilities are not the same.

In particular for text entries, there are two types of fields:
* keyword fields, that are used for exact matching
* full text fields, where part of the text can be matched, with complex matching possibilities

There are also numeric and date fields, that can be used for range matching, or to make computations.

## Full text queries

**FIXME** add more on how we transform queries

## Filtering by language

By default, the `langs` parameter only selects which language-specific
subfields are searched (e.g., `product_name.de` instead of `product_name.fr`).
It does **not** restrict which products appear in results.

To restrict results to products actually available in the requested languages,
use the `filter_by_langs=true` parameter alongside `langs`:

```
GET /search?q=Apfel&langs=de&filter_by_langs=true
```

This adds an Elasticsearch `terms` filter on the `languages_codes` field,
using OR semantics (a product is included if it is available in *any* of the
requested languages).

**Important notes:**

- The pseudo-language `main` is ignored when building the filter.
- If all requested languages are `main` (or the list is empty after excluding
  `main`), no filter is applied.
- The index must have been built with a `languages_codes` keyword field in the
  configuration. If the field is absent, the API returns an error.
- Adding `languages_codes` to an existing index requires a **full re-index**.
  See [How to update an index](how-to-update-index.md) for details.
