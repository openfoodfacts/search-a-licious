import {LitElement, html} from 'lit';
import {customElement, property, state} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';

import {EventRegistrationMixin} from './event-listener-setup';
import {SearchResultEvent} from './events';
import {SearchaliciousEvents} from './enums';
import {
  MissingResultTemplateError,
  MultipleResultTemplateError,
} from './errors';

// we need it to declare functions
type htmlType = typeof html;

/**
 * The search results element
 *
 * It will display results based upon the slot with name `result`,
 * considered as a template, with variable interpolation (using tag-params library).
 *
 * It reacts to the `searchalicious-result` event fired by the search controller.
 */
@customElement('searchalicious-results')
export class SearchaliciousResults extends EventRegistrationMixin(LitElement) {
  /**
   * the search we display result for,
   * this corresponds to `name` attribute of corresponding search-bar
   */
  @property({attribute: 'search-name'})
  searchName = 'searchalicious';

  // did we already launched a search
  @state()
  searchLaunched = false;

  // the last search results
  @state()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  results: Record<string, any>[] = [];

  // attribute giving id to seek in search results, might be undefined
  @property({attribute: 'result-id'})
  resultId = '';

  /**
   * A function rendering a single result. We define this just to get it's prototype right.
   *
   * It will be replaced by a dynamic function created
   * from the content of the slot named result.
   *
   * Note that we need to pass along html, because at rendering time, it will not be available as a global
   */
  resultRenderer = function (html: htmlType, result: Object, index: number) {
    const data = html`Please provide a template`;
    if (!result && !index) {
      // just to make TS happy that we use the variables
      // eslint-disable-next-line no-empty
    }
    return data;
  };

  /**
   * HTML to display when there are no results
   *
   * Can be overridden by a "no-results" slot
   */
  noResults = html`<div>No results found</div>`;

  /**
   * HTML to display before anysearch is launched
   *
   * Can be overridden by a "before-search" slot
   */
  beforeSearch = html``;

  /**
   * Build a result renderer from the template provided by user.
   * It creates dynamically a function that renders the template with the given result and index.
   * This is the best way I could find !
   * It is faster as using eval as the function is built only once at component creation time.
   * @returns Function (htmlType, Object, string) => TemplateResult<ResultType>
   */
  _buildResultRenderer() {
    const resultTemplate = this._getTemplate('result');
    return Function(
      'html',
      'result',
      'index',
      'return html`' + resultTemplate + '`;'
    ) as typeof this.resultRenderer;
  }

  /**
   * Get the template for one result, using `<slot name="<name>">`
   * This must be run before shadowRoot is constructed ! (to be able to grab this.innerHTML)
   */
  _getTemplate(name: string) {
    // const fragment = new DocumentFragment();
    // fragment.replaceChildren(document.createElement("template"));
    // (fragment.firstChild! as HTMLElement).append(this.innerHTML);
    const fragment = document.createElement('div');
    fragment.innerHTML = this.innerHTML;

    //const element = new DOMParser().parseFromString(`<template>${this.innerHTML}</template>`, "text/html");
    const slots = fragment.querySelectorAll(`[slot="${name}"]`);
    // we only need one !
    if (!slots || slots.length === 0) {
      throw new MissingResultTemplateError(`No slot found with name="${name}"`);
    } else if (slots.length > 1) {
      throw new MultipleResultTemplateError(
        `Multiple slots found with name="${name}"`
      );
    }
    return slots[0].innerHTML;
  }

  override render() {
    if (this.results.length) {
      return this.renderResults();
    } else if (this.searchLaunched) {
      return html`<slot name="no-results">${this.noResults}</slot>`;
    } else {
      return html`<slot name="before-search">${this.beforeSearch}</slot>`;
    }
  }

  renderResults() {
    // we have a keyFn only if this.resultId exists
    // compute params to repeat according to that
    const renderResult = (result: Object, index: number) =>
      this.resultRenderer(html, result, index);
    const keyFn = this.resultId
      ? (result: Record<string, unknown>) => result[this.resultId] as string
      : undefined;
    const KeyFnOrTemplate = keyFn ? keyFn : renderResult;
    const templateOrUndef = keyFn ? renderResult : undefined;
    return html` <ul part="results">
      ${repeat(this.results, KeyFnOrTemplate, templateOrUndef)}
    </ul>`;
  }

  /**
   * event handler for NEW_RESULT events
   */
  _displayResults(event: Event) {
    // check if event is for our search
    const detail = (event as SearchResultEvent).detail;
    if (detail.searchName === this.searchName) {
      this.searchLaunched = true;
      this.results = detail.results; // it's reactive, should trigger rendering
    }
  }

  /**
   * Create our resultRenderer, using last opportunity to read innerHTML before shadowRoot creation.
   * Also connect search event handlers.
   */
  override connectedCallback() {
    // we do this before calling super, to be sure we still have our innerHTML intact
    // note: we don't do it in constructor, because it would disable using document.createElement
    // as _buildResultRenderer needs the slot named result to already exists
    this.resultRenderer = this._buildResultRenderer();
    super.connectedCallback();
    this.addEventHandler(SearchaliciousEvents.NEW_RESULT, (event) =>
      this._displayResults(event)
    );
  }
  // connect to our specific events
  override disconnectedCallback() {
    super.disconnectedCallback();
    this.removeEventHandler(SearchaliciousEvents.NEW_RESULT, (event) =>
      this._displayResults(event)
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-results': SearchaliciousResults;
  }
}
