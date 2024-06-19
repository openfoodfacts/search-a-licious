# Search-a-licious Web Frontend

The search-a-licious web frontend supplies web components.
These are built using [lit](https://lit.dev) and [typescript](https://www.typescriptlang.org/).

## Widgets

The project is currently composed of several widgets

* searchalicious-bar is at the core, it represent the search bar, but also handle the search logic (see searchalicious-ctl.ts)
* searchalicious-button is a simple button to launch the search
* searchalicious-results is the component that displays the search results
  * you must provide an element with attribute `slot="result"` that contains a template to display a single search result.
    It's a good idea to use a `template` as enclosing element with `style="display: none"`,
    to avoid displaying weird content while the page loads,
    and to put a `loading="lazy"`on images so that
    the browser does not try to fetch urls with non resolved expressions in them.
  * a `before-search` slot is also available to display something before first search launch
  * as well as a `no-results` slot to display something when no results are found
* searchalicious-pages is the component that displays the pagination
  * you can specify the number of displayed pages with `displayed-pages` attribute
  * there are `before-search` and `no-results` slots
* searchalicious-facets is a container for facets (helpers to filter search results)
  * it must contains some actual facets
  * it will influence the search adding filters
* searchalicious-facet-terms renders the facet for terms (list of entries, with number of docs).
  * it must be in a `searchalicious-facets`
  * the user can select facets to filter the search
* searchalicious-autocomplete is a component that displays a list of suggestions
  * it must be in a `searchalicious-facet`
  * it will influence the search adding terms to the search
* searchalicious-checkbox is a simple checkbox
  * it can be used to replace the default checkbox
  * it allows to keep the state of the checkbox when you change the property
* searchalicious-secondary-button is a button with defined style
  * it can be used to replace the default button
* searchalicious-button-transparent is a transparent button with defined style
  * it can be used to replace the default button
* searchalicious-chart renders vega chart, currently only for distribution. Requires [vega](https://vega.github.io/).

You can give a specific `name` attribute to your search bar.
Then all other component that needs to connect with this search must use the same value in `search-name` attribute

## Explanation on code structure

We use web-components for they will enable integration in a very wide variety of situations.

The `search-ctl.ts` file contains the search controller, which is responsible for launching search and dispatching results. In practice this is a mixin, used by the search bar components which gets this role of controller. It is the contact point with the API.
The controller have a specific name, and components that are linked to it refer this the search bar name (`search-name` property). The default is 'searchalicious'.

Components communicate with the search controller thanks to events, see `events.ts`.
There is an event to launch a search or change page, and one to dispatch search results.
Events always contains the search name, so we could have more than one search on the same page.

We tend to factor code when it make sense using mixins,
for example as there are lots of component that needs the search results, there is a mixin than contains the logic to register to such events (see `search-results-ctl.ts`).


## Tools

Thanks to Makefile in root folder,

* `make check_front` run all checks in front
* `make lint_front` lint js code

While coding, you might want to run: `make tsc_watch` to have your code compile every time you save a `.ts` file.

## Tests

`make test_front` run js tests.

Note that we use:
* [Open Web Component testing framework](https://open-wc.org/docs/testing/testing-package/),
  which in turn use:
  * [Mocha](https://mochajs.org/) as the test runner
  * which run tests using [playwright](https://playwright.dev/)
  * and [Chai](https://www.chaijs.com/) for assertions

## Translations
To translate we use [lit-localize](https://lit.dev/docs/localization/overview/), which is a library that uses lit-element to handle translations.
The translations are stored in the `translations` folder in the root of the project.

To add a new translation you need to :
- add `msg` in your code like this https://lit.dev/docs/localization/overview/#message-types
- run `npm run extract:translations` to extract the new translations
- add your translation with 'target' tag in the `xliff/<your_language>.xlf` files
- run `npm run build:translations` to update the translations in the `src/generated/locales/<your_language>.js` file

### Translations in Crowdin
We use Crowdin to manage translations. 
All files in the `xliff/` folder are automatically uploaded to Crowdin. 
When translations are done, they are automatically downloaded to the `xliff/` folder.

## Credits

This part of the project was bootstrap using [lit-element-starter-ts](https://github.com/lit/lit-element-starter-ts/).
