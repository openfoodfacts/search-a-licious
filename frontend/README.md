# Search-a-licious Web Frontend

The search-a-licious web frontend supplies web components. These are built using lit and typescript.


This part of the project was bootstrap using [lit-element-starter-ts](https://github.com/lit/lit-element-starter-ts/).

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