# Search-a-licious Web Frontend

See [Explain frontend](../docs/devs/explain-web-frontend.md) for an introduction.

## Credits

This part of the project was bootstrapped using [lit-element-starter-ts](https://github.com/lit/lit-element-starter-ts/).


## Widgets

**FIXME: all this docs should be moved to the JSDocs of the components**
which can be displayed in the [reference documentation for web components](https://openfoodfacts.github.io/search-a-licious/users/ref-web-components/)

### Main widgets

* **searchalicious-bar** is at the core, it represent the search bar, but also handle the search logic (see searchalicious-ctl.ts)
* **searchalicious-results** is the component that displays the search results
  * you must provide an element with attribute `slot="result"` that contains a template to display a single search result.
    It's a good idea to use a `template` as enclosing element with `style="display: none"`,
    to avoid displaying weird content while the page loads,
    and to put a `loading="lazy"`on images so that
    the browser does not try to fetch urls with non resolved expressions in them.
  * a `before-search` slot is also available to display something before first search launch
  * as well as a `no-results` slot to display something when no results are found
* **searchalicious-pages** is the component that displays the pagination
  * you can specify the number of displayed pages with `displayed-pages` attribute
  * there are `before-search` and `no-results` slots
* **searchalicious-sort** is a button to choose a sort order
  * you must add **searchalicious-sort-field** elements inside to add sort options
    * with a field= to indicate the field
    * the label is the text inside the element
  * or a **searchalicious-sort-script**
    * with a script= to indicate a script
    * and a params= which is a either a json encoded object, 
      or a key in localStorage prefixed with "local:"
  * you can add element to slot `label` to change the label
* **searchalicious-facets** is a container for facets (helpers to filter search results)
  * it must contains some actual facets
  * it will influence the search adding filters
* **searchalicious-chart** renders vega chart, currently only for distribution. Requires [vega](https://vega.github.io/).

### Layout widgets
Layout widgets are used to layout the page, they are not mandatory but can be useful.
It must not create dependencies with other components.

* searchalicious-panel-manager is a component below body to wrap all lit components
  * it allows to have a global variable to store with @lit/context
* searchalicious-layout-page is a component to layout the page
  * it allows to handle sidebars

**IMPORTANT:**
You can give a specific `name` attribute to your search bar.
Then all other component that needs to connect with this search must use the same value in `search-name` attribute.
This enables supporting multiple searches in the same page


### Secondary widgets

* **searchalicious-button** is a simple button to launch the search
* **searchalicious-count** is a simple counter of the  number of search results


### Internal widgets
* **searchalicious-facet-terms** renders the facet for terms (list of entries, with number of docs).
  * it must be in a `searchalicious-facets`
  * the user can select facets to filter the search
* **searchalicious-suggestion-entry** is a component that displays a list of suggestions
  * it must be in a `searchalicious-facet`
  * it will influence the search adding terms to the search
* **searchalicious-checkbox** is a simple checkbox
  * it can be used to replace the default checkbox
  * it allows to keep the state of the checkbox when you change the property
* **searchalicious-radio** is a simple radio button
  * it can be used to replace the default radio button
  * it allows to keep the state of the radio button when you change the property
  * You can unchecked the radio button by clicking on it
* **searchalicious-toggle** is a simple toggle button
  * it can be used to replace the checkbox
  * it allows to keep the state of the toggle button when you change the property
* **searchalicious-secondary-button** is a button with defined style
  * it can be used to replace the default button
* **searchalicious-button-transparent** is a transparent button with defined style
  * it can be used to replace the default button
* **searchalicious-icon-cross** is a cross icon
    * it can be used to delete actions
* **searchalicious-suggestion-entry** is a suggestion entry
    * it can be used to display a suggestion in searchalicious-bar



