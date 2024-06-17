# Thoughts on scoring

## Using scripts

This is the easiest method, and more generic one, but not necessarily optimize for big databases.

* scripts can be declared in the config
* we run a command to store them in Elasticsearch (removing the eventual non declared ones)
``
* (maybe at startup we should verify that the scripts declared in config are in ElasticSearch)
* scripts accepts parameters
* as you call search API, you specify a script name (as in config) and provide parameters

It can be used for ranking and to compute specific attributes

Pros:
* it can be secure as we provide scripts in the config
* it's a simple design, easy to implement

Cons:
* performance might be an issue if there is no filters

Filters might be a way to improve performances ?

Performance might be better when people use vectors and vectors functions like dotProduct.
This means supporting vectors in fields types.

Having well designed filters to limit the score, might also help.
Is there a way we put a maximum number of matching item before using a filter ?

Also the script filter may help, if it's faster than score to remove some values (but is it worth it ?)

## Using KNN

There is a good support for KNNs in ElasticSearch, with approximate matching.

If we can reduce scoring to a KNN search this might be worth exploring.

It can be combined with filters.

But we might need to limit pagination as there is no way to really use pagination in this context.
A filter might be used to remove first pages ids, but it is limited.

## Personal search at Open Food Facts

The score is a ponderated mean, so really it can be seen as a dotProduct

We can put attributes match in a vector and put weighs of user attributes in another vector,
then use dotProduct. ( a1 * b1 + a2 * b2 + a3 * b3)

It is ok for ranking as "maybe" and "unknown" are not taken into account.

The only problem is with "non matching" we should be less than 0 and is hard to express in a dotProduct
(non matching is as soon as a mandatory is < 10).
This could be expressed by adding to the vector a special part where all attributes under 10 are 128 and 0 otherwise for the product, and for the parameter, we put -128 in the corresponding slot if attribute is mandatory.

We can use byte vectors as values are between 0 and 100, which helps being fast. It also aleviate the constraint of having 
score is 0.5 + (dot_product(query, vector) / (32768 * dims)), so to retrieve the dot product you should do
(score - 0.5) * 32768 * dims


## Current conclusions

* start with implementing scripts score, in config, and enable their usage in the API
* enable having vector fields
* explore performance on this basis
* see if we can expose knn instead ?
* maybe expose available scripts in an api ?