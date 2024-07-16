# Explain scripts

You can use scripts to sort results in your search requests.

This leverage a possibility of Elasticsearch of [script based sorting](https://www.elastic.co/guide/en/elasticsearch/reference/current/sort-search-results.html#script-based-sorting).

Using scripts needs the following steps:

1. [declare the scripts than can be used in the configuration](#declare-the-script-in-the-configuration)
2. [import the scripts in Elasticsearch](#import-the-script-in-elasticsearch)
3. call the search API using the script name, and providing parameters


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

See [introduction to script in Elasticsearch documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/modules-scripting-using.html)

## Import the scripts in Elasticsearch

Each time you change the configuration, you have to import the scripts in Elasticsearch.

For this you only need to run the sync-scripts command.

```bash
docker compose run --rm api python -m app sync-scripts
```


## Using the script in the API

After

## Performance considerations

When you use scripts for sorting, bare in mind that they needs to be executed on each document.

Tests your results on your full dataset to make sure performances are not an issue.

An heavy load on scripts sorting might affect other requests as well under an heavy load.

