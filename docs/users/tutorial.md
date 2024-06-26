# Tutorial - Using search-a-licious in your project

So you have a dataset, or a project, with a collection of data you want to make searchable.
Search-a-licious can help you have it done in a matter of few hours, while retaining your choices.

In this tutorial, we will see how we can use search-a-licious to search Open Food Facts data.

## Setting up

### Clone the repository

As an easy way to setup the project we will clone the repository:

```bash
git clone git@github.com:openfoodfacts/search-a-licious.git
cd search-a-licious
```

### Create a configuration file

We need to create a configuration file to indicate which fields we care about in our index.

For this we can create a conf/data/openfoodfacts-tutorial.yml file. It uses the [YAML format](https://yaml.org/).

At the top we have:

```yaml
default_index: "off" # see 2
indices:  # see 1
  off:    # see 2
```

1. Search-a-licious support serving more than one dataset at once,
  each dataset as it's own indice with it's own definition.
  So we start with the "indices" keyword.

2. We must give a name to our unique index. Let's call it `off` as Open Food Facts.
  We also indicate that this is the default index for the API.

Now comes important indications for the index:
```yaml
...
indices:
  off:
    index:  # see 1
      id_field_name: code  # see 2
      last_modified_field_name: last_modified_t  # see 2
      name: openfoodfacts  # see 3
```

1. The index section mark settings that are specific to the index.
2. We have to then indicate two important fields:
   * a field that contains a unique id for each item in the collection (the identifier).
     In Open Food Facts dataset, it's simply the barcode, stored in `code`
    * a field that contains the item modification date to enable incremental updates.
      In Open Food Facts dataset, it's `last_modified_t`
3. We have to give a sensible name to the index, which should be unique for our ElasticSearch instance.
   So we simply put "openfoodfacts".

Let's continue with configuration of fields we want to be able to search.

```yaml
...
indices:
  off:
    ...
    fields:  # see 1
      code:  # see 2
        required: true
        type: keyword
      product_name:  # see 3
        full_text_search: true
        type: text_lang
      labels_tags:  # see 4
        type: keyword
        taxonomy_name: label
        bucket_agg: true
      labels:  # see 5
        full_text_search: true
        input_field: labels_tags
        taxonomy_name: label
        type: taxonomy
      nutriscore_grade:  # see 6
        type: keyword
        bucket_agg: true
      last_modified_t:  # see 7
        type: date
```

1. now we are in the field section
2. code is our identifier, it contains the barcode
  * we mark it required for we should reject elements without it (it's certainly a bug)
  * Each field must have a type which indicates how to handle it.
  * For the code we choose the type `keyword` which means it's a fixed token.
3. product_name is also an important field.
  * this time we want to be able to search part of it,
    also it's a field that comes with different values for different languages,
    that's why we mark it as `type: textlang`
  * We also include this field in free text search,
    that's the `full_text_search: true` part.
4. `labels_tags` is a field that contains labels of the product in a canonical form.
  * This is a field supported by a taxonomy.
    Taxonomies gives translations and synonyms for terms of a specific field of interest.
    In this case this is the `label` taxonomy. We will see later on the configuration of taxonomies.
    This field will be useful to find all items matching a particular label in a precise way,
    using the label canonical form.
  * Also we plan to use the field for facets so we put the `bucket_agg: true` part.
5. The labels repeat information from `labels_tags`
   (hence the `input_field: labels_tags`)
   but is there to enrich the information of full text searches
   (`type: taxonomy`).
   With that, the full text search will take into account the translations and synonyms of labels.
6. Nutri-Score is a field with very basic values: "a", "b", ..., "e", "unknown" and "not-applicable",
  as for code, a perfect case for a `keyword` field
7. last_modified_t, corresponding to last modification time, is an example of a date field.

Let's continue with configuration of taxonomies.

Taxonomies will be used in multiple ways by *search-a-licious*:
* to add synonyms for taxonomized values on full text search.
  For example you might search for *"European Organic"*,
  to find items with the *"EU Organic"* label.
* to suggest values to search for in autocomplete (this can also be used in edit forms)
* to translate values from the results, for example as we display facets

```yaml
...
indices:
  off:
    ...
    taxonomy:
      sources:  # see 1
      - name: label
        url: https://static.openfoodfacts.org/data/taxonomies/labels.full.json
      exported_langs:   # see 2
      - en
      - fr
      index:   # see 3
        name: off_taxonomy
```

1. We cited one taxonomy above: `label`, here we define how to get it.
2. We must also defined which languages we want to use for this taxonomy.
   There is some trade-off between having a manageable size for the index and supporting more languages.
3. finally we have to give a name to the Elasticsearch index that will contain the taxonomies.

We continue with languages configurations:

```yaml
...
...
indices:
  off:
    ...
    supported_langs: ["en", "fr"]
    lang_separator: "_"
```
1. the list of supported languages tells which languages will be retained in our index
2. the "lang separator" helps us tells that, the fields are suffixed by the language using this separator.
  In our case it means, for example, that `product_name_fr` contains the french version of `product_name`.

We have our configuration ready. That was a bit though, but this was the hardest part !

### Setup the project

In the project you can modify the `.env` file and change variables you need to change,
but for now, the only mandatory variable to change
is the one that will point to our configuration file.

```ini
...
# Path to the yaml configuration file
# This envvar is **required**
CONFIG_PATH=`data/config/openfoodfacts.yml`
```

## Initial import

### Getting the data

Now that it's all done, we are ready to start to import the data.

First we start the Elasticsearch index,
we will also start the ElasticVue service to be able to look at what happens:
```bash
docker compose up -d es01 es02 elasticvue
```

There is an export of all the openfoodfacts data in JSONL available on at 
https://static.openfoodfacts.org/data . But it's a very big file ! 
For this tutorial we will prefer to use a sample of products
at https://static.openfoodfacts.org/data/products.random-modulo-10000.jsonl.gz

Put this file in the data/ directory which is bind mounted in the container.
On linux we can do it with:
```bash
wget https://static.openfoodfacts.org/data/products.random-modulo-10000.jsonl.gz -O data/products.random-modulo-10000.jsonl.gz
```

### Import the data

We will then import this file in our index, we have a specific command for that:

```bash
docker compose run --rm api python3 -m app import /opt/search/data/products.random-modulo-10000.jsonl' args='--skip-updates
```

The first part is simply to run a command using our docker container.
The `python3 -m app import` part is to run the `import` command provided by our `app` module.

We use the `--skip-updates` flag because we don't have a redis stream to connect to, to look for updates.

We also need our taxonomy, and there is a command `import-taxonomies` to get it.

```bash
docker compose run --rm api python3 -m app import-taxonomies
```

### Inspecting Elasticsearch

We can take a look at what just happened by using ElasticVue, a simple but handy tool to inspect Elasticsearch.

Open http://127.0.0.1:8080 in your browser.

If it's the fist time, click "ADD ELASTICSEARCH CLUSTER" and use "No authorization",
cluster name: docker-cluster, uri: http://localhost:9200

Click on the button which says there are 3 indices.

You shall see two indices:
* one named `openfoodfacts-<date of initial import>` with alias `openfoodfacts`
* one named `off_taxonomy-<date of initial import>` with alias `off_taxonomy`
As you already guessed, the first contains our food products, and the second our taxonomies.

![Our two indices in ElasticVue](../assets/tutorial-elasticvue-indices-after-import.png "Our two indices in ElasticVue")

The "Lucene docs" column gives you an idea of the number of entries you have in each index.

You can click on an index to view it's content and have a feeling of what we just imported.

## Using the search API



We don't have an interface to search at the moment, but we can use the API.

It would be perfectly ok to only deploy the interface,
maybe because you will call it from your own application either to provide search to your users,
or to implement a very specific feature which is based upon a search request.

Let's start our search-a-licious service:

```bash
docker compose up  es01 es02 api frontend
```

We start the `api` container, which is the search-a-licious backend,
and the frontend as it is a nginx acting as a reverse proxy.

Now let's open http://127.0.0.1:8000/docs

You can see the documentation of the various API offered by search-a-licious service.

Let's concentrate on the *GET* `/search` service. We can test it using the *Try it out* button.

We can try a simple search of *fair trade* in the q parameter, we get 17 results.

Interesting fields in the JSON we receive includes:

* `hits` where we have the detail of each result
* `page`: the current returned page, `page_count` the number of pages, and `page_size` the number of results per page.
* `count` is the total number of items returned.
  `is_count_exact`, when false indicate that for performance reason, we did not compute the total number of results,
  but there are at least `count` results.

We may want to be more precise on our request. Now let's ask products which really have "fair-trade" label.