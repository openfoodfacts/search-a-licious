

# JSON schema for search-a-licious configuration file

<p>This is the global config object that reflects
the yaml configuration file.

Validations will be performed while we load it.</p>

<table>
<tbody>

<tr><th>$schema</th><td>https://json-schema.org/draft/2019-09/schema</td></tr>
</tbody>
</table>

## Properties

<table class="jssd-properties-table"><thead><tr><th colspan="2">Name</th><th>Type</th></tr></thead><tbody><tr><td colspan="2"><a href="#indices">indices</a></td><td>Object</td></tr><tr><td colspan="2"><a href="#default_index">default_index</a></td><td>String</td></tr></tbody></table>



<hr />


## indices


<table class="jssd-property-table">
  <tbody>
    <tr>
      <th>Title</th>
      <td colspan="2">Indices</td>
    </tr>
    <tr>
      <th>Description</th>
      <td colspan="2">configuration of indices. The key is the ID of the index that can be referenced at query time. One index corresponds to a specific set of documents and can be queried independently.</td>
    </tr>
    <tr><th>Type</th><td colspan="2">Object</td></tr>
    <tr>
      <th>Required</th>
      <td colspan="2">Yes</td>
    </tr>
    
  </tbody>
</table>




## default_index


<table class="jssd-property-table">
  <tbody>
    <tr>
      <th>Title</th>
      <td colspan="2">Default Index</td>
    </tr>
    <tr>
      <th>Description</th>
      <td colspan="2">the default index to use when no index is specified in the query</td>
    </tr>
    <tr><th>Type</th><td colspan="2">String</td></tr>
    <tr>
      <th>Required</th>
      <td colspan="2">Yes</td>
    </tr>
    
  </tbody>
</table>









<hr />

## Schema
```
{
    "$defs": {
        "ESIndexConfig": {
            "properties": {
                "name": {
                    "description": "name of the index alias to use",
                    "title": "Name",
                    "type": "string"
                },
                "id_field_name": {
                    "description": "name of the field to use for `_id`.it is mandatory to provide one.\n\n If your dataset does not have an identifier field, you should use a document preprocessor to compute one.",
                    "title": "Id Field Name",
                    "type": "string"
                },
                "last_modified_field_name": {
                    "description": "name of the field containing the date of last modification, used for incremental updates using Redis queues. The field value must be an int/float representing the timestamp.\n\n",
                    "title": "Last Modified Field Name",
                    "type": "string"
                },
                "number_of_shards": {
                    "default": 4,
                    "description": "number of shards to use for the index",
                    "title": "Number Of Shards",
                    "type": "integer"
                },
                "number_of_replicas": {
                    "default": 1,
                    "description": "number of replicas to use for the index",
                    "title": "Number Of Replicas",
                    "type": "integer"
                }
            },
            "required": [
                "name",
                "id_field_name",
                "last_modified_field_name"
            ],
            "title": "ESIndexConfig",
            "type": "object"
        },
        "FieldConfig": {
            "properties": {
                "name": {
                    "default": "",
                    "description": "name of the field, must be unique",
                    "title": "Name",
                    "type": "string"
                },
                "type": {
                    "allOf": [
                        {
                            "$ref": "#/$defs/FieldType"
                        }
                    ],
                    "description": "type of the field, see `FieldType` for possible values"
                },
                "required": {
                    "default": false,
                    "description": "if required=True, the field is required in the input data",
                    "title": "Required",
                    "type": "boolean"
                },
                "input_field": {
                    "anyOf": [
                        {
                            "type": "string"
                        },
                        {
                            "type": "null"
                        }
                    ],
                    "default": null,
                    "description": "name of the input field to use when importing data",
                    "title": "Input Field"
                },
                "split": {
                    "default": false,
                    "description": "do we split the input field with `split_separator` ?\n\nThis is useful if you have some text fields that contains list of values, (for example a comma separated list of values, like apple,banana,carrot).\n\nYou must set split_separator to the character that separates the values in the dataset.",
                    "title": "Split",
                    "type": "boolean"
                },
                "full_text_search": {
                    "default": false,
                    "description": "do we include perform full text search using this field. If false, the field is only used during search when filters involving this field are provided.",
                    "title": "Full Text Search",
                    "type": "boolean"
                },
                "bucket_agg": {
                    "default": false,
                    "description": "do we add an bucket aggregation to the elasticsearch query for this field. It is used to return a 'faceted-view' with the number of results for each facet value. Only valid for keyword or numeric field types.",
                    "title": "Bucket Agg",
                    "type": "boolean"
                },
                "taxonomy_name": {
                    "anyOf": [
                        {
                            "type": "string"
                        },
                        {
                            "type": "null"
                        }
                    ],
                    "default": null,
                    "description": "the name of the taxonomy associated with this field. It must only be provided for taxonomy field type.",
                    "title": "Taxonomy Name"
                },
                "add_taxonomy_synonyms": {
                    "default": true,
                    "description": "if True, add all synonyms of the taxonomy values to the index. The flag is ignored if the field type is not `taxonomy`.",
                    "title": "Add Taxonomy Synonyms",
                    "type": "boolean"
                }
            },
            "required": [
                "type"
            ],
            "title": "FieldConfig",
            "type": "object"
        },
        "FieldType": {
            "enum": [
                "keyword",
                "date",
                "half_float",
                "scaled_float",
                "float",
                "double",
                "integer",
                "short",
                "long",
                "unsigned_long",
                "bool",
                "text",
                "text_lang",
                "taxonomy",
                "disabled",
                "object"
            ],
            "title": "FieldType",
            "type": "string"
        },
        "IndexConfig": {
            "description": "Inside the config file we can have several indexes defined.\n\nThis object gives configuration for one index.",
            "properties": {
                "index": {
                    "allOf": [
                        {
                            "$ref": "#/$defs/ESIndexConfig"
                        }
                    ],
                    "description": "configuration of the Elasticsearch index"
                },
                "fields": {
                    "additionalProperties": {
                        "$ref": "#/$defs/FieldConfig"
                    },
                    "description": "configuration of all fields in the index, keys are field names and values contain the field configuration",
                    "title": "Fields",
                    "type": "object"
                },
                "split_separator": {
                    "default": ",",
                    "description": "separator to use when splitting values, for fields that have split=True",
                    "title": "Split Separator",
                    "type": "string"
                },
                "lang_separator": {
                    "default": "_",
                    "description": "for `text_lang` FieldType, the separator between the name of the field and the language code, ex: product_name_it if lang_separator=\"_\"",
                    "title": "Lang Separator",
                    "type": "string"
                },
                "primary_color": {
                    "default": "#aaa",
                    "description": "Used for vega charts. Should be html code.",
                    "title": "Primary Color",
                    "type": "string"
                },
                "accent_color": {
                    "default": "#222",
                    "description": "Used for vega. Should be html code.and the language code, ex: product_name_it if lang_separator=\"_\"",
                    "title": "Accent Color",
                    "type": "string"
                },
                "taxonomy": {
                    "allOf": [
                        {
                            "$ref": "#/$defs/TaxonomyConfig"
                        }
                    ],
                    "description": "configuration of the taxonomies used"
                },
                "supported_langs": {
                    "description": "A list of all supported languages, it is used to build index mapping",
                    "items": {
                        "type": "string"
                    },
                    "title": "Supported Langs",
                    "type": "array"
                },
                "document_fetcher": {
                    "description": "The full qualified reference to the document fetcher, i.e. the class responsible from fetching the document using the document ID present in the Redis Stream.",
                    "examples": [
                        "app.openfoodfacts.DocumentFetcher"
                    ],
                    "title": "Document Fetcher",
                    "type": "string"
                },
                "preprocessor": {
                    "anyOf": [
                        {
                            "description": "The full qualified reference to the preprocessor to use before data import. This is used to adapt the data schema or to add search-a-licious specific fields for example.",
                            "examples": [
                                "app.openfoodfacts.DocumentPreprocessor"
                            ],
                            "type": "string"
                        },
                        {
                            "type": "null"
                        }
                    ],
                    "default": null,
                    "title": "Preprocessor"
                },
                "result_processor": {
                    "anyOf": [
                        {
                            "description": "The full qualified reference to the elasticsearch result processor to use after search query to Elasticsearch. This is used to add custom fields for example.",
                            "examples": [
                                "app.openfoodfacts.ResultProcessor"
                            ],
                            "type": "string"
                        },
                        {
                            "type": "null"
                        }
                    ],
                    "default": null,
                    "title": "Result Processor"
                },
                "scripts": {
                    "anyOf": [
                        {
                            "additionalProperties": {
                                "$ref": "#/$defs/ScriptConfig"
                            },
                            "description": "You can add scripts that can be used for sorting results",
                            "type": "object"
                        },
                        {
                            "type": "null"
                        }
                    ],
                    "default": null,
                    "title": "Scripts"
                },
                "match_phrase_boost": {
                    "default": 2,
                    "description": "How much we boost exact matches on individual fields",
                    "title": "Match Phrase Boost",
                    "type": "number"
                },
                "document_denylist": {
                    "description": "list of documents IDs to ignore",
                    "items": {
                        "type": "string"
                    },
                    "title": "Document Denylist",
                    "type": "array",
                    "uniqueItems": true
                },
                "redis_stream_name": {
                    "anyOf": [
                        {
                            "type": "string"
                        },
                        {
                            "type": "null"
                        }
                    ],
                    "default": null,
                    "description": "name of the Redis stream to read from when listening to document updates. If not provided, document updates won't be listened to for this index.",
                    "title": "Redis Stream Name"
                }
            },
            "required": [
                "index",
                "fields",
                "taxonomy",
                "supported_langs",
                "document_fetcher"
            ],
            "title": "IndexConfig",
            "type": "object"
        },
        "ScriptConfig": {
            "description": "Scripts can be used to sort results of a search.\n\nThis use ElasticSearch internal capabilities",
            "properties": {
                "lang": {
                    "allOf": [
                        {
                            "$ref": "#/$defs/ScriptType"
                        }
                    ],
                    "default": "expression",
                    "description": "The script language, as supported by Elasticsearch"
                },
                "source": {
                    "description": "The source of the script",
                    "title": "Source",
                    "type": "string"
                },
                "params": {
                    "anyOf": [
                        {
                            "description": "Params for the scripts. We need this to retrieve and validate parameters",
                            "type": "object"
                        },
                        {
                            "type": "null"
                        }
                    ],
                    "title": "Params"
                },
                "static_params": {
                    "anyOf": [
                        {
                            "description": "Additional params for the scripts that can't be supplied by the API (constants)",
                            "type": "object"
                        },
                        {
                            "type": "null"
                        }
                    ],
                    "title": "Static Params"
                }
            },
            "required": [
                "source",
                "params",
                "static_params"
            ],
            "title": "ScriptConfig",
            "type": "object"
        },
        "ScriptType": {
            "enum": [
                "expression",
                "painless"
            ],
            "title": "ScriptType",
            "type": "string"
        },
        "TaxonomyConfig": {
            "description": "Configuration of taxonomies,\nthat is collections of entries with synonyms in multiple languages\n\nField may be linked to taxonomies.",
            "properties": {
                "sources": {
                    "description": "configurations of used taxonomies",
                    "items": {
                        "$ref": "#/$defs/TaxonomySourceConfig"
                    },
                    "title": "Sources",
                    "type": "array"
                },
                "exported_langs": {
                    "description": "a list of languages for which we want taxonomized fields to be always exported during indexing. During indexing, we use the taxonomy to translate every taxonomized field in a language-specific subfield. The list of language depends on the value defined here and on the optional `taxonomy_langs` field that can be defined in each document.",
                    "items": {
                        "type": "string"
                    },
                    "title": "Exported Langs",
                    "type": "array"
                },
                "index": {
                    "allOf": [
                        {
                            "$ref": "#/$defs/TaxonomyIndexConfig"
                        }
                    ],
                    "description": "configuration of the taxonomy index. There is a single index for all taxonomies."
                }
            },
            "required": [
                "sources",
                "exported_langs",
                "index"
            ],
            "title": "TaxonomyConfig",
            "type": "object"
        },
        "TaxonomyIndexConfig": {
            "description": "We have an index storing multiple taxonomies\n\nIt enables functions like auto-completion, or field suggestions\nas well as enrichment of requests with synonyms",
            "properties": {
                "name": {
                    "description": "name of the taxonomy index alias to use",
                    "title": "Name",
                    "type": "string"
                },
                "number_of_shards": {
                    "default": 4,
                    "description": "number of shards to use for the index",
                    "title": "Number Of Shards",
                    "type": "integer"
                },
                "number_of_replicas": {
                    "default": 1,
                    "description": "number of replicas to use for the index",
                    "title": "Number Of Replicas",
                    "type": "integer"
                }
            },
            "required": [
                "name"
            ],
            "title": "TaxonomyIndexConfig",
            "type": "object"
        },
        "TaxonomySourceConfig": {
            "properties": {
                "name": {
                    "description": "name of the taxonomy",
                    "title": "Name",
                    "type": "string"
                },
                "url": {
                    "description": "URL of the taxonomy, must be in JSON format and follows Open Food Facts taxonomy format.",
                    "format": "uri",
                    "maxLength": 2083,
                    "minLength": 1,
                    "title": "Url",
                    "type": "string"
                }
            },
            "required": [
                "name",
                "url"
            ],
            "title": "TaxonomySourceConfig",
            "type": "object"
        }
    },
    "description": "This is the global config object that reflects\nthe yaml configuration file.\n\nValidations will be performed while we load it.",
    "properties": {
        "indices": {
            "additionalProperties": {
                "$ref": "#/$defs/IndexConfig"
            },
            "description": "configuration of indices. The key is the ID of the index that can be referenced at query time. One index corresponds to a specific set of documents and can be queried independently.",
            "title": "Indices",
            "type": "object"
        },
        "default_index": {
            "description": "the default index to use when no index is specified in the query",
            "title": "Default Index",
            "type": "string"
        }
    },
    "required": [
        "indices",
        "default_index"
    ],
    "title": "JSON schema for search-a-licious configuration file",
    "type": "object",
    "$schema": "https://json-schema.org/draft/2019-09/schema"
}
```


