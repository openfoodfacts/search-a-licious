# Explain configuration file

The idea of Search-a-licious is that you provide all your configurations details in a central file,
and all the rest works (at least for main scenarios).

The configuration file is a YAML file.

## One configuration, multiple datasets

A Search-a-licious instance only have one configuration file,
but is capable of serving multiple datasets

It provides a section for each index you want to create (corresponding to a dataset).

If you have more than one dataset, one must be declared the default (see [default_index](../ref-config/searchalicious-config-schema.html#default_index))

## Main sections

For each indexe the main sections are:

* index: some configuration of the Elasticsearch index
* fields: the fields you want to put in the index, their type and other configurations
* taxonomy: definitions of taxonomies that are used by this index
* redis_stream_name and document_fetcher: if you use continuous updates, you will need to define one
* preprocessor and result_processor are two fields enabling to handle specificities of your dataset.
* scripts: to use sort by script (see [How to use scripts](./how-to-use-scripts.md))


## Index configuration

Search-a-licious is really based upon Elasticsearch,

This section provides some important fields to control the way it is used.

`id_field_name` is particularly important as it must contain a field that uniquely identifies each items.
If you don't have such field, you might use `preprocessor` to compute one.
It is important to have such an id to be able to use [continuous updates](FIXME).

`last_modified_field_name` is also important to decide whether we should update an item
and avoid indexing an item that is rapidly changing more than necessary.

## Fields

This is one of the most important section.

It specifies what will be stored in your index,
which fields will be searchable, and how.

You have to plan in advance how you configure this.

Think well about:
* fields you want to search and how you want to search them
* which informations you need to display in search results
* what you need to sort on
* which facets you want to display
* which charts you need to build

Changing this section will probably involve a full re-indexing of all your items.

Read more in the [reference documentation](../ref-config/searchalicious-config-schema.html#fields).

## Document fetcher, pre-processors and post-processors

It is not always straight forward to index an item.

Search-a-licious offers a way for you to customize some critical operations using Python code.

* preprocessor adapts you document before being indexed
* whereas result_processor adapts each result returned by a search, keep it lightweight !
* document_fetcher is only used for continuous updates to fetch documents using an API

Read more in the [reference documentation](../ref-config/searchalicious-config-schema.html).

## Scripts

You can also add scripts for sorting documents. See [How to use scripts](./how-to-use-scripts.md).