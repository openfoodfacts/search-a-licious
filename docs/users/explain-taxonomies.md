# Explain taxonomies

Taxonomies are a way to organize categorization of items.

Normally a taxonomy is about a specific field.
For each possible values, it defines translations in different languages, and also possible synonyms (in each languages).
For each entry we have a canonical identifier.

A taxonomy also organize the entries within a direct acyclic graph (a hierarchy but with possibility of multiple parents, though always avoiding cycles).
For example it may help describe that a salmon is a marine fish as well as a freshwater fish, and a oily fish.

It can be used to help users find items using a specific field, in their language, even if they use a synonym for it.

## Listing taxonomies

If you plan to use taxonomies, you should first list them, in the [taxonomy section of the configuration](./ref-config/searchalicious-config-schema.html#indices_additionalProperties_taxonomy).

Taxonomies must come in a JSON format, that can be downloaded at a particular URL.

The data in the JSON must contains an object, where:
* each key correspond to the id of the taxonomy entries
* the value is an Object, with the following fields (none are mandatory):
  * `name`: an Object associating language code,
    with the entry name in the language (useful for translating the entry)
  * `synonyms`: an Object associating language code,
    with an array of synonyms for this entry in this language

## Taxonomy fields

As you define your [fields in the configuration](./explain-configuration.md#fields),
you can specify that a field is a taxonomy field (`type: taxonomy`).

In this case, you also have to provide following fields:
* taxonomy_name: the name of the taxonomy (as defined in the configuration)

* synonyms_search: if true,
  this will add a full text subfield that will enable using synonyms and translations to match this term.


## Autocompletion with taxonomies

When you import taxonomies, they can be used to provide autocompletion in multiple ways.

The webcomponents can use them to add values to facets,
or to provide suggestions in the search bar.

You can also use the [autocompletion API](../ref-openapi/#operation/taxonomy_autocomplete_autocomplete_get)

## Importing taxonomies

If you defined taxonomies,
you must import them using the [import-taxonomies command](../devs/ref-python/cli.html#python3-m-app-import-taxonomies).
