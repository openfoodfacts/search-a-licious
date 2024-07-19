# Explain configuration file

The idea of Search-a-licious is that you provide all your configurations details in a central file,
and all the rest works (at least for main scenarios).

The configuration file is a YAML file.

## One configuration, multiple datasets

A Search-a-licious instance only have one configuration file,
but is capable of serving multiple datasets

It provides a section for each index you want to create (corresponding to a dataset).

If you have more than one dataset, one must be declared the default (see [default_index](./searchalicious-config-schema.html#default_index))

## Main sections

For each indexe the main sections are:

* index: some configuration of the Elasticsearch index
* fields: the fields you want to put in the index, their type and other configurations
* taxonomy: definitions of taxonomies that are used by this index
* redis_stream_name and document_fetcher: if you use continuous updates, you will need to define one
* preprocessor and result_processor are two fields enabling to handle specificities of your dataset.
* scripts: to use sort by script (see [How to use scripts](./how-to-use-scripts.md))

## Index configuration

You must provide the 

## Fields