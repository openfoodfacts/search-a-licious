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

```
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
      labels:  # see 4
        full_text_search: true
        input_field: labels_tags
        taxonomy_name: label
        type: taxonomy
      nutriscore_grade:  # see 5
        type: keyword
      last_modified_t:  # see 6
        type: date
```

1. now we are in the field section
2. code is our identifier, it contains the barcode
  * we mark it required for we should reject elements without it (it's certainly a bug)
  * Each field must have a type which indicates how to handle it.
  * For the code we choose the type `keyword` which means it's a fixed token.
3. product_name is also an important field.
  * this time we want to be able to search part of it, also it's a field that comes with translations.that's why we mark it as 

### Setup the project

In the project you can modify the .env file and change variables you need to change,
but for now, the only mandatory variable to change
is the one that will point to our configuration file.
10


