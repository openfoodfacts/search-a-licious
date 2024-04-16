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

  // the search results
  @state()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  results: Record<string, any>[] = [];

  // attribute giving id
  @property({attribute: 'result-id'})
  resultId = 'id';

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

  // override constructor to generate the result renderer function
  constructor() {
    super();
    this.resultRenderer = this._buildResultRenderer();
  }

  /**
   * Build a result renderer from the template provided by user.
   * It creates dynamically a function that renders the template with the given result and index.
   * This is the best way I could find !
   * It is faster as using eval as the function is built only once at component creation time.
   * @returns Function (htmlType, Object, string) => TemplateResult<ResultType>
   */
  _buildResultRenderer() {
    const resultTemplate = this._getTemplate();
    return Function(
      'html',
      'result',
      'index',
      'return html`' + resultTemplate + '`;'
    ) as typeof this.resultRenderer;
  }

  /**
   * Get the template for one result, using `<slot name="result">`
   * This must be run in constructor ! (to be able to grab this.innerHTML)
   */
  _getTemplate() {
    // const fragment = new DocumentFragment();
    // fragment.replaceChildren(document.createElement("template"));
    // (fragment.firstChild! as HTMLElement).append(this.innerHTML);
    const fragment = document.createElement('div');
    fragment.innerHTML = this.innerHTML;

    //const element = new DOMParser().parseFromString(`<template>${this.innerHTML}</template>`, "text/html");
    const slots = fragment.querySelectorAll('slot[name="result"]');
    // we only need one !
    if (!slots || slots.length === 0) {
      throw new MissingResultTemplateError('No slot found with name="result"');
    } else if (slots.length > 1) {
      throw new MultipleResultTemplateError(
        'Multiple slots found with name="result"'
      );
    }
    return slots[0].innerHTML;
  }

  override render() {
    const renderResult = this.resultRenderer;
    console.dir(this.results[0]);
    return html` <ul part="results">
      ${repeat(
        this.results,
        (result) => result[this.resultId] as string,
        (result, index) => renderResult(html, result, index)
      )}
    </ul>`;
  }

  _displayResults(event: Event) {
    // check if event is for our search
    const detail = (event as SearchResultEvent).detail;
    if (detail.searchName === this.searchName) {
      this.results = detail.results; // it's reactive, should trigger rendering
    }
  }

  // connect to our specific events
  override connectedCallback() {
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
