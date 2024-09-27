# Developer introduction

The Search-a-licious project is centered around a few main components:
* The API, using FastAPI, that you find in **`app` folder**. See it's [ref documentation](./ref-python.md)
* The web components to build your UI, using [Lit](https://lit.dev/) that you find in **`frontend` folder**.
  See [Explain frontend](./explain-web-frontend.md)
* Docker compose for deployment, see **`docker-compose.yml` and `docker/` folder**

We use three main components:
* [Elasticsearch](https://www.elastic.co/elasticsearch) for the search engine[^OpenSearchWanted]
* [Redis] for event stream[^AltRedisWanted]
* [Vega](https://vega.github.io/) for the charts


see [Explain Architecture](./explain-architecture.md) for more information.

## Getting started

See [Install the project locally for development](./how-to-install.md)


## Development tips

* [How to debug the backend](./how-to-debug-backend.md)


[^OpenSearchWanted]: [Open Search](https://opensearch.org/) is also a desirable target, contribution to verify compatibility and provide it as default would be appreciated.

[^AltRedisWanted]: an alternative to Redis for event stream would also be a desirable target.


