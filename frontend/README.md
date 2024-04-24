# Search-a-licious Web Frontend

The search-a-licious web frontend supplies web components. These are built using lit and typescript.

## Widgets

The project is currently composed of several widgets

* searchalicious-bar is at the core, it represent the search bar, but also handle the search logic (see searchalicious-ctl.ts)
* searchalicious-button is a simple button to launch the search
* searchalicious-results is the component that displays the search results
  * you must provide an element with attribute `slot="result"` that contains a template to display a single search result
  * a `before-search` slot is also available to display something before first search launch
  * as well as a `no-results` slot to display something when no results are found


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

## Credits

This part of the project was bootstrap using [lit-element-starter-ts](https://github.com/lit/lit-element-starter-ts/).
