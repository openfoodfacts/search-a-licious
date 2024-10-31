# Reference for Search-a-licious Web Components

This page documents [web Components](https://developer.mozilla.org/en-US/docs/Web/API/Web_components)
provided by Search-a-licious
to quickly build your interfaces.

See the [tutorial for an introduction](./tutorial.md#building-a-search-interface)

## Customization

### Styling

We added a lot of `part` attributes to the components, to allow you to customize the look and feel of the components. See [::part() attribute documentation on MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/::part)

### Translations

We only translated basic messages and most labels can generally be overridden using slots inside web component, where your own translation framework might be use (be it in javascript, or through your template engine or any technique).

If you however needs to override current translations, you might clone this project, change translations in xliff files and regenerate the bundle.

## Main components

Those are the components you will certainly use to build your interface.
Of course none are mandatory and you can pick and choose the components you need.

Bare attention to the `search-name` attribute
which must correspond to the `name` attribute of the search bar.
If you do not specify it, it will be the default one.
You'll need it if you mix multiple search bars in the same page.

### searchalicious-bar

<api-viewer src="./dist/custom-elements.json" only="searchalicious-bar"></api-viewer>

### searchalicious-results
<api-viewer src="./dist/custom-elements.json" only="searchalicious-results"></api-viewer>

### searchalicious-pages

<api-viewer src="./dist/custom-elements.json" only="searchalicious-pages">

### searchalicious-taxonomy-suggest

<api-viewer src="./dist/custom-elements.json" only="searchalicious-suggest"></api-viewer>

### searchalicious-facets

<api-viewer src="./dist/custom-elements.json" only="searchalicious-sort">

### searchalicious-button

<api-viewer src="./dist/custom-elements.json" only="searchalicious-button">

### searchalicious-count

<api-viewer src="./dist/custom-elements.json" only="searchalicious-count">

## Sorting

### searchalicious-sort

<api-viewer src="./dist/custom-elements.json" only="searchalicious-sort">

### searchalicious-sort-field

<api-viewer src="./dist/custom-elements.json" only="searchalicious-sort-field">

### searchalicious-sort-script

<api-viewer src="./dist/custom-elements.json" only="searchalicious-sort-script">


## Charts components

Charts components are based on [vega](https://vega.github.io/).

### searchalicious-distribution-chart

<api-viewer src="./dist/custom-elements.json" only="searchalicious-distribution-chart">


### searchalicious-scatter-chart

<api-viewer src="./dist/custom-elements.json" only="searchalicious-scatter-chart">


## Layout components

Layout widgets are used to layout the page, they are not mandatory but can be useful.
It must not create dependencies with other components.

### searchalicious-panel-manager

<api-viewer src="./dist/custom-elements.json" only="searchalicious-panel-manager">

### searchalicious-layout-page

<api-viewer src="./dist/custom-elements.json" only="searchalicious-panel-manager">


## Internal components

Those are components that are not intended to be used directly by the user,
but are used internally by the other components.

### searchalicious-facet-terms

<api-viewer src="./dist/custom-elements.json" only="searchalicious-facet-terms">

### searchalicious-suggestion-entry

<api-viewer src="./dist/custom-elements.json" only="searchalicious-suggestion-entry">

### searchalicious-checkbox

<api-viewer src="./dist/custom-elements.json" only="searchalicious-checkbox">

### searchalicious-radio

<api-viewer src="./dist/custom-elements.json" only="searchalicious-radio">

### searchalicious-toggle

<api-viewer src="./dist/custom-elements.json" only="searchalicious-toggle">

### searchalicious-secondary-button

<api-viewer src="./dist/custom-elements.json" only="searchalicious-secondary-button">

### searchalicious-button-transparent

<api-viewer src="./dist/custom-elements.json" only="searchalicious-button-transparent">

### searchalicious-icon-cross

<api-viewer src="./dist/custom-elements.json" only="searchalicious-icon-cross">

### searchalicious-suggestion-entry

<api-viewer src="./dist/custom-elements.json" only="searchalicious-suggestion-entry">


<!-- api-viewer element library -->
<script type="module" src="https://jspm.dev/api-viewer-element"></script>
