# How to use scripts

You can use scripts to sort results in your search requests.

It enables to provides results that depends upon users defined preferences.

This leverage a possibility of Elasticsearch of [script based sorting](https://www.elastic.co/guide/en/elasticsearch/reference/current/sort-search-results.html#script-based-sorting).

Using scripts needs the following steps:

1. [declare the scripts than can be used in the configuration](#declare-the-script-in-the-configuration)
2. [import the scripts in Elasticsearch](#import-the-script-in-elasticsearch)
3. either use web-components to sort using scripts or call the search API using the script name, and providing parameters


## Declare the script in the configuration

You have to declare the scripts that can be used for sorting in your configuration.

This has two advantages:
* this keeps the API call simple, by just refering to the script by name
* this is more secure as you are in full control of scripts that are allowed to be used.

The scripts section can look something like this:
```yaml
    scripts:
      personal_score: # see 1
        # see https://www.elastic.co/guide/en/elasticsearch/painless/8.14/index.html
        lang: painless  # see 2
        # the script source, here a trivial example
        # see 3
        source: |-
          doc[params["preferred_field"]].size > 0 ? doc[params["preferred_field"]].value : (doc[params["secondary_field"]].size > 0 ? doc[params["secondary_field"]].value : 0)
        # gives an example of parameters
        # see 4
        params:
          preferred_field: "field1"
          secondary_field: "field2"
        # more non editable parameters, can be easier than to declare constants in the script
        # see 5
        static_params:
          param1 : "foo"
```

Here:
1. we declare a script named `personal_score`, this is the name you will use in your API requests and/or web-components attributes

2. we declare the language of the script, in this case `painless`, search-a-licious supports [painless](https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-painless.html) and [Lucene expressions](https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-expression.html)

3. this is the source of the script. It can be a bit tedious to write those scripts. You can use the [Elasticsearch documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-painless.html) to get a better understanding of the language.

  In this example we are using a one liner, but your scripts can be far more complex.

4. Parameters are a way to add inputs to the script.
   You can declare them using an example. You can provide more complex structures, as allowed by JSON.
   Those parameters will be given through the API requests

5. static_params are parameters that are not allowed to change through the API.
   It's mostly a way to declare constants in the script.
   (hopefully more convenient than declaring them in the script)

For more information on configuration for scripts see [configuration reference](./ref-config/searchalicious-config-schema.html#indices_additionalProperties_scripts)

For informations on how to write scripts,
see [introduction to script in Elasticsearch documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-using.html)

## Import the scripts in Elasticsearch

Each time you change the configuration, you have to import the scripts in Elasticsearch.

For this you only need to run the sync-scripts command.

```bash
docker compose run --rm api python -m app sync-scripts
```

## Using web components

After you have registered a script, it can be used for sorting using Search-a-licious provided web components.

We imagine that you already have setup a search page, with, at least a `searchalicious-bar` (eventually refer to [tutorial on building a search interface](./tutorial.md#building-a-search-interface)).

In your [`searchalicious-sort`](./ref-web-components/#searchalicious-sort) component, you can add multiple sort options.
While [`searchalicious-sort-field`](./ref-web-components/#searchalicious-sort-field) component add sorting on a field,
you can use [`searchalicious-sort-script`](./ref-web-components/#searchalicious-sort-script) to add sorting on a script.

This component has:
- an attribute to set the script name, corresponding to the name you have declared in the configuration.
- an attribute to set the parameters for this sort option.
  This in turn can:
  - either be a string encoding a JSON Object (if your parameters are in some way static, or you set them through javascript)
  - either be a key corresponding to a value in the local storage.
    In this case it must be prefixed with `storage:`, and the value must be the key in the local storage.

Using static parameters can be an option if you are reusing the same script but for different scenarios.
Imagine you have a script like the one given in example above,
you could reuse the script to sort either on portion size or quantity (if no portion size),
or to sort on nutriscore or sugar per 100g (if no nutriscore).

Note that in this case you must provide an `id` to at least one of the sort option
(because default id is based on script name).

```html
<searchalicious-sort>
  <searchalicious-sort-script
    script="personal_score"
    id="sort-by-quantity"
    parameters='{"preferred_field": "portion_size", "secondary_field": "quantity"}'
  >
    Sort by portion size (fallback on quantity)
  </searchalicious-sort-script>
  <searchalicious-sort-script
    script="personal_score"
    id="sort-by-nutrition"
    parameters='{"preferred_field": "nutriscore", "secondary_field": "sugar_per_100g"}'
  >
    Sort by Nutri-Score (fallback on sugar per 100g)
  </searchalicious-sort-script>
</searchalicious-sort>
```

On the other side, using dynamic parameters can be an option if you want to let the user choose the field to sort on.
For this you will need an independant way to set the values to sort on (your own UI) that either:
- dynamically modifies your searchalicious-sort-script element to change parameters property
- either stores it in local storage

The later option as the advantage that it will survive a reload of the page or be still present on another visit.
```html
<searchalicious-sort>
  <searchalicious-sort-script
    script="personal_score"
    parameters='local:personal-score-params'
  >
    Sort according to my preferences
  </searchalicious-sort-script>
</searchalicious-sort>
```

## Using the script in the API

You might also want to use the sort by script option in the API.

For this:
* you must issue a POST request to the `/api/search` endpoint
* you must pass a JSON payload with:
  * the script name in the `sort_by` property
  * you must provide the `sort_params`  property with a valid JSON object, corresponding to your parameters.

Let's use the same example as above, we could launch a search on whole database using our `personal_script` script, using curl
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{
    "sort_by": "personal_score",
    "sort_params": {"preferred_field": "nutriscore", "secondary_field": "sugar_per_100g"}
  }' \
  http://localhost:8000/api/search
```

## Privacy considerations

The sort by script option was designed to allow users to sort their results according to their preferences.

In the context of Open Food Facts, those preferences can reveal data which should remain privates.

That's why we enforce using a `POST` request in the API (to avoid accidental logging),
and we try hard not to log this data inside search-a-licious.

## Performance considerations

When you use scripts for sorting, bare in mind that they needs to be executed on each document.

Tests your results on your full dataset to make sure performances are not an issue.

An heavy load on scripts sorting might affect other requests as well under an heavy load.

