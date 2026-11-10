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

### Update daemon checkpoints

The daemon records its position in the event stream in Redis, after each handled event:

* the key is `searchalicious:checkpoint:<stream name>:<index name>`,
  where the index name is the index (alias) the events are written to
  (the same stream used for two indexes has therefore two checkpoints) ;
* the value is the Redis stream ID of the last handled event.

When the daemon restarts (deployment, crash, Elasticsearch or Redis outage),
it resumes from this checkpoint, so events published while it was not running are not lost.
Transient errors are retried with an exponential backoff instead of crashing the process.

If there is no checkpoint yet (first run, or after deleting the key),
the daemon starts from the most recent document of the index, using
the [`last_modified_field_name` from the configuration](./ref-config/searchalicious-config-schema.html#indices_additionalProperties_index_last_modified_field_name).

Hence, the index must be populated before the daemon can start.
**If the index is empty, the daemon waits for it to be filled** (by an import),
checking regularly, instead of skipping the events published until then.
It processes no event until the index has at least one document.

A successful import (`import` command, unless `--skip-updates` is used)
moves the checkpoint to the most recent imported document,
so the daemon does not replay events that the import already took into account.

To force the daemon to start again from the most recent indexed document, delete the key:
```bash
# replace <stream name> and <index name> with your values
docker-compose exec redis redis-cli DEL searchalicious:checkpoint:<stream name>:<index name>
```

### Monitoring the update daemon

Besides its checkpoint, the daemon stores some information about its processing in Redis,
under the key `searchalicious:updates_state:<stream name>:<index name>` (a hash):

* `last_read_id`: the Redis stream ID of the last event the daemon read ;
* `pending_events`: how many events the daemon has read and still has to process.

This state is informational only: writing it is throttled (at most once every 10 seconds,
plus once when the stream is quiet and on shutdown) and a failure to record it never
affects the indexing of the events.

It is reported by the `/health` API endpoint, in the `update-daemon-state` check
(these fields never change the health status of the API):

```json
{
  "update-daemon-state": {
    "streams": [
      {
        "index": "off",
        "stream": "product_updates_off",
        "last_read_id": "1762775912345-0",
        "last_message_timestamp_ms": 1762775912345,
        "last_message_age_seconds": 12.4,
        "pending_events": 4
      }
    ]
  }
}
```

`last_message_age_seconds` is computed when the endpoint is queried, from the timestamp of
`last_read_id`: **it keeps growing if the daemon stops**, which is the signal to watch
(beware that an idle stream naturally makes it grow as long as no event is published).
Note that the check result is cached by the health check library for about 30 seconds:
`last_message_age_seconds` is the age at the time reported in the `timestamp` field of
the `update-daemon-state` check result, not at the time of the request.
The fields are `null` if the daemon never recorded its state.

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

