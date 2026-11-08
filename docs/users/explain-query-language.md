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
  "dark chocolate" AND (labels:organic OR labels:vegan) AND NOT nutriscore_grade:(e OR d)
  ```
  Entries with text `dark chocolate`, labels containing `organic` or `vegan`, and Nutri-Score not `e` or `d`
* you can query a sub field of an object by using "." between the field and the sub field
  (the ":" form is not valid):
  ```
  nutriments.sugars_100g:[10 TO 15]
  ```
  Entries with sugar between 10 and 15 grams per 100g
* in range you can use * for unbounded values:
  ```
  nutriments.sugars_100g:[* TO 20] AND nutriments.proteins_100g:[2 TO *]
  ```
  Entries with sugar below 20 g and proteins above 2g for 100g
* match field existence with `*`:
  ```
  nutriscore_grade:*
  ```
  Entries with Nutri-Score computed

## Different type of fields

When you created you configuration, you defined different fields types.
It's important because the matching possibilities are not the same.

In particular for text entries, there are two types of fields:
* keyword fields, that are used for exact matching
* full text fields, where part of the text can be matched, with complex matching possibilities

There are also numeric and date fields, that can be used for range matching, or to make computations.

### Taxonomy fields

What you can write after `labels:` depends on the
[`synonyms_strategy`](./explain-taxonomies.md#taxonomy-fields) of your index:

* with `index`, you can use a name or a synonym, in any language of the request:
  `labels:organic`, `labels:bio`
* with `none`, the field only contains taxonomy ids, so you must use the id,
  with its language prefix: `labels:"en:organic"`.
  A bare `labels:organic` matches nothing.

## Full text queries

A word or a quoted phrase without a field name is searched in all the fields
that have `full_text_search: true` in the configuration.
For fields that have one text per language,
only the languages of the request (the `langs` parameter) are searched.

* a word matches if it is found in any of those fields
* a quoted phrase matches if the words are found next to each other, in the same order
* `*` and `?` can be used inside a word (`choco*`, `milk?`),
  but `*` alone is refused because it would match everything
* the `boost_phrase` parameter of the API favors entries where the words of the query
  are consecutive, even if you did not use quotes

Queries are transformed before being sent to Elasticsearch,
this is how the languages and your configuration are taken into account.