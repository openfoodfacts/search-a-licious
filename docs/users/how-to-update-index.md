# How to update the index

As you use search-a-licious, you will first import the data,
but then, you might need to update the index to keep it up to date with the latest data.

There are two strategies to update the index:
* either you push events to the redis stream, and search-a-licious update the index continuously
* either you update the index from time to time using a new import of whole dataset

## First import

First import will populate Elasticsearch index with all the data.

See [*initial import* section in tutorial](./tutorial.md#initial-import)
and [`import` reference documentation](../devs/ref-python/cli.html#python3-m-app-import)

It's important to note that if you don't use the *continous updates* strategy,
you need to use `--skip-updates` option.

## Continuous updates

To have continuous updates, you need to push events to the redis stream.

Normally this will be done by your application.

On each update/removal/etc. it must push events with at least:
* the document id
* and eventually more info (if you need them to filter out items, for example).

Of course you can also imagine to push events from another service,
if you have another way of getting changes, but this part is up to you.

Then you just have to run the `updater` container that comes in the docker-compose configuration.
```bash
docker-compose up -d updater
```

This will continuously fetch updates from the event stream, and update the index accordingly.

At start it will compute last update time using
the [`last_modified_field_name` from the configuration](./ref-config/searchalicious-config-schema.html#indices_additionalProperties_index_last_modified_field_name)
to know from where to start processing the event stream.

## Updating the index from time to time with an export

Another way to update the index is to periodically re-import the all the data, or changed data.

This is less compelling to your users, but this might be the best way
if you are using an external database publishing changes on a regular bases.

For that you can use the [`import` command](../devs/ref-python/cli.html#python3-m-app-import),
with the `--skip-updates` option, and with the `--partial` option if you are importing only changed data
(otherwise it is advised to use the normal import process, which can be rolled-back (it create a new index)).

## Document fetcher and pre-processing

In the configuration, you can define a
[`document_fetcher`](./ref-config/searchalicious-config-schema.html#indices_additionalProperties_document_fetcher)
and a [`preprocessor`](./ref-config/searchalicious-config-schema.html#indices_additionalProperties_preprocessor) to transform the data.

Those are fully qualified dotted names to python classes.

`document_fetcher` is only used on continuous updates,
while `preprocessor` is used both on continuous updates and on initial import.

