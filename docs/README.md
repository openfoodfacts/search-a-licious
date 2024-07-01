# Search-a-licious

Welcome to the documentation of search-a-licious,
a ready to use search component built on top of [Elasticsearch](https://www.elastic.co/).

We created this project in order to leverage collections of (uniform enough) data
to build tools that can:
* make this data reachable by a large public
* help users find the right items according to their criteria
* enable data exploration and get useful insights

It provides a ready to use component to:
* provide an engaging search experience with
  * a fast full text search
  * facets to refine results
  * as you type filter suggestions
* personalize results to specific needs thanks to specific sorting
* help your users build insights with instant charts
* build powerful in app features thanks to a powerful API

On a technical level, you can use:
* web components to quickly build your UI using any javascript framework, or plain HTML
* sensible defaults to provide a good search experience
* an easy to setup, one stop, file configuration to describe your content
* a ready to deploy docker compose file including all needed services
* a one command initial data import from a jsonl data export
* continuous update through a stream of events

It leverage existing components:
* [Elasticsearch](https://www.elastic.co/elasticsearch) for the search engine[^OpenSearchWanted]
* [Web Components](https://developer.mozilla.org/en-US/docs/Web/API/Web_Components) (built thanks to [Lit framework](https://lit.dev/))
* [Vega](https://vega.github.io/) for the charts
* [Redis] for event stream[^AltRedisWanted]

[^OpenSearchWanted]: [Open Search](https://opensearch.org/) is also a desirable target, contribution to verify compatibility and provide it as default would be appreciated.

[^AltRedisWanted]: an alternative to Redis for event stream would also be a desirable target.


## documentation organization

The documentation is split between User documentation (for re-users, third party developers) and Developer documentation (for contributors).

The documentation follows the [Diátaxis framework](https://diataxis.fr/).

Pages title should start with:
* *tutorial on* - tutorials aimed at learning
* *how to…* - how to guides to reach a specific goal
* *explain…* - explanation to understand a topic
* *reference…* - providing detailed information