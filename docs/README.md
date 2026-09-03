# Search-a-licious

![Search-a-licious](./assets/RVB_HORIZONTAL_WHITE_BG_SEARCH-A-LICIOUS-50.png "Search-a-licious logo")

Welcome to the documentation of search-a-licious,
a ready to use search component built on top of [Elasticsearch](https://www.elastic.co/).

## Quick Navigation

**👥 For Users & Integrators:**
- 🚀 [**Get Started with Tutorial**](./users/tutorial.md) - Step-by-step guide to set up your first search interface
- 📋 [**Installation Guide**](./users/how-to-install.md) - Deploy Search-a-licious with Docker
- 🔧 [**Configuration Reference**](./users/ref-config.md) - Complete configuration options
- 🔍 [**Query Language Guide**](./users/explain-query-language.md) - Master the search syntax
- 🌐 [**Web Components**](./users/ref-web-components.md) - Building UI with web components

**🛠️ For Contributors & Developers:**
- 💡 [**Development Introduction**](./devs/introduction.md) - Get started contributing
- 🏗️ [**Architecture Overview**](./devs/explain-architecture.md) - Understand the system design
- 🔧 [**Installation for Development**](./devs/how-to-install.md) - Set up development environment
- 🐛 [**Debugging Guide**](./devs/how-to-debug-backend.md) - Debug backend issues
- 📚 [**Python Reference**](./devs/ref-python.md) - API documentation

## Executive summary

Search-a-licious transforms large data collections into searchable content, allowing users to quickly find what they need with powerful queries, facet exploration, and visualizations. Originally developed for Open Food Facts, it’s perfect for exposing data, supporting decision-making, and enabling exploration, unlocking the full potential of open data collections. Developers can rapidly build apps thanks to its easy configuration, reusable components, and robust architecture.

## What is search-a-licious ?

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

## Technical overview

On a technical level, you can use:
* [web components](./users/tutorial.md#building-a-search-interface) to quickly build your UI using any JavaScript framework, or plain HTML
* sensible defaults to provide a good search experience
* an easy to setup, [one stop, file configuration](./users/tutorial.md#create-a-configuration-file) to describe your content
* a [ready to deploy Docker Compose file](./users/how-to-install.md) including all needed services
* a [one command initial data import](./users/tutorial.md#import-the-data) from a JSONL data export
* [continuous update](./users/how-to-update-index.md) through a stream of events

It leverages existing components:
* [Elasticsearch](https://www.elastic.co/elasticsearch) for the search engine
* [Web Components](https://developer.mozilla.org/en-US/docs/Web/API/Web_Components) (built thanks to [Lit framework](https://lit.dev/))
* [Vega](https://vega.github.io/) for the charts
* [Redis](https://redis.io/) for event stream

[Read our tutorial](./users/tutorial.md) to get started !

## Contributing

This is an Open Source project and contributions are really welcome !

See our [developer introduction to get started](./devs/introduction.md)

Every contribution as bug report, documentation, UX design is also really welcome !
See our [wiki page about Open Food Facts](https://wiki.openfoodfacts.org/Search-a-licious)

## 🎨 Design Resources

- [![Figma](https://img.shields.io/badge/figma-%23F24E1E.svg?logo=figma&logoColor=white) Search-a-Licious logo](https://www.figma.com/design/gNnI56OF91Ugdd4fBaq5F8/Search-A-Licious-Logo?m=auto&t=bEHMawF1eequkY9w-6)
- [![Figma](https://img.shields.io/badge/figma-%23F24E1E.svg?logo=figma&logoColor=white) Wireframes & Mood board](https://www.figma.com/design/d1tuhFa0qQLqqJP2xbwBqZ/Website-%E2%80%93%3E-Search?node-id=1-2&t=bEHMawF1eequkY9w-0)

## documentation organization

The documentation is split between User documentation (for re-users, third party developers) and Developer documentation (for contributors).

The documentation follows the [Diátaxis framework](https://diataxis.fr/).

Pages title should start with:
* *tutorial on* - tutorials aimed at learning
* *how to…* - how to guides to reach a specific goal
* *explain…* - explanation to understand a topic
* *reference…* - providing detailed information


## Thank you to our sponsors !

This project has received financial support from the NGI Search (New Generation Internet) program, funded by the 🇪🇺 European Commission. Thank you for supporting Open-Source, Open Data, and the Commons.

<img src="./assets/NGISearch_logo_tag_icon.svg" alt="NGI-search logo" title="NGI-search logo" height="100" />  
<img src="./assets/europa-flag.jpg" alt="European flag" title="The European Union flag" height="100" />
