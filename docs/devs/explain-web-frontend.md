# Explain web frontend

The search-a-licious web frontend supplies web components.
These are built using [lit](https://lit.dev) and [typescript](https://www.typescriptlang.org/).

You can find the documentation for each widget in the [Reference for Search-a-licious Web Components](../users/ref-web-components.md) file.


## Explanation on code structure

We use web-components for they will enable integration in a very wide variety of situations.

The `search-ctl.ts` file contains the search controller, which is responsible for launching search and dispatching results. In practice this is a mixin, used by the search bar components which gets this role of controller. It is the contact point with the API.
The controller have a specific name, and components that are linked to it refer this the search bar name (`search-name` property). The default is 'searchalicious'.

Components communicate with the search controller thanks to events, see `events.ts`.
There is an event to launch a search or change page, and one to dispatch search results.
Events always contains the search name, so we could have more than one search on the same page.

We tend to factor code when it make sense using mixins,
for example as there are lots of component that needs the search results, there is a mixin than contains the logic to register to such events (see `search-results-ctl.ts`).

## Writing documentation

We render the reference on web components using [`api-viewer`](https://api-viewer.open-wc.org/docs) web component.

Please comply with JSDoc and [document every property / slots](https://api-viewer.open-wc.org/docs/guide/writing-jsdoc/) etc. on each web components.

## Tools

Thanks to Makefile in root folder,

* `make check_front` run all checks in front
* `make lint_front` lint js code

While coding, you might want to run: `make tsc_watch` to have your code compile every time you save a `.ts` file.

We generate a [custom-elements.json manifest](https://github.com/webcomponents/custom-elements-manifest) using [custom elements manifest analyzer](https://custom-elements-manifest.open-wc.org/analyzer).
Please use supported [JSDoc markers](https://custom-elements-manifest.open-wc.org/analyzer/getting-started/#supported-jsdoc) in your code to document components.

The components documentation is rendered in `web-components.html`, using the [api-viewer component](https://api-viewer.open-wc.org/)

## Tests

`make test_front` run js tests.

Note that we use:
* [Open Web Component testing framework](https://open-wc.org/docs/testing/testing-package/),
  which in turn uses:
  * [Mocha](https://mochajs.org/) as the test runner
  * which runs tests using [playwright](https://playwright.dev/)
  * and [Chai](https://www.chaijs.com/) for assertions

## Translations

In the frontend, we utilize [lit-localize](https://lit.dev/docs/localization/overview/), a library that leverages lit-element for managing translations from hardcoded text.
The language is set to the browser's language if it is supported by the project, otherwise it is set to default language (English).
The translations are stored in `xliff` files in the `frontend/xliff` directory.

To add a new translation you need to :
- add `msg` in your code like this https://lit.dev/docs/localization/overview/#message-types
- run `npm run translations:extract` to extract the new translations
- add your translation with 'target' tag in the `xliff/<your_language>.xlf` files
- run `npm run translations:build` to update the translations in the `src/generated/locales/<your_language>.js` file

To add a language, you have to add the language code to `targetLocales` in `lit-localize.json`


### Translations in Crowdin

We can use Crowdin to manage translations.
All files in the xliff/ folder can be uploaded to Crowdin, as it supports the [xlf format](https://store.crowdin.com/xliff).
