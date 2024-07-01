import {LitElement, html, css} from 'lit';
import {customElement, property, state} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';

import {SearchaliciousResultCtlMixin} from './mixins/search-results-ctl';
import {SearchResultEvent} from './events';
import {
  MissingResultTemplateError,
  MultipleResultTemplateError,
} from './errors';
import {localized, msg} from '@lit/localize';
import {SignalWatcher} from '@lit-labs/preact-signals';
import {isSearchLoading} from './signals';

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
@localized()
export class SearchaliciousResults extends SignalWatcher(
  SearchaliciousResultCtlMixin(LitElement)
) {
  static override styles = css`
    .loading {
      height: 300px;
      border-radius: 8px;
      animation: loading 2.25s ease infinite;
      box-shadow: 0 4px 4px rgba(0, 0, 0, 0.25);
      background-color: var(--first-loading-color, #cacaca);
    }

    @keyframes loading {
      0% {
        background-color: var(--first-loading-color, #cacaca);
      }
      50% {
        background-color: var(--second-loading-color, #bbbbbb);
      }
      100% {
        background-color: var(--first-loading-color, #cacaca);
      }
    }
  `;

  // the last search results
  @state()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  results: Record<string, any>[] = [];

  // attribute giving id to seek in search results, might be undefined
  @property({attribute: 'result-id'})
  resultId = '';

  @property({attribute: 'loadind-card-size', type: Number})
  loadingCardSize = 200;

  /**
   * The parent width, used to compute the number of loading cards to display
   */
  get parentWidth() {
    return this.parentElement?.offsetWidth || 1200;
  }

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
  get noResults() {
    return html`<div>${msg('No results found')}</div>`;
  }

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

  /**
   * Render the loading cards
   * We display 2 columns of loading cards
   */
  renderLoading() {
    // we take the row width and display 2 columns of loading cards
    const numCols = Math.floor(this.parentWidth / this.loadingCardSize) * 2;

    return html`
      <slot name="loading">
        <ul part="results-loading">
          ${Array(numCols)
            .fill(0)
            .map(() => html`<li part="result-loading" class="loading"></li>`)}
        </ul>
      </slot>
    `;
  }

  override render() {
    if (this.results.length) {
      return this.renderResults();
      // if we are loading, we display the loading cards
    } else if (isSearchLoading(this.searchName).value) {
      return this.renderLoading();
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
  override handleResults(event: SearchResultEvent) {
    this.results = event.detail.results; // it's reactive, should trigger rendering
  }

  /**
   * Create our resultRenderer, using last opportunity to read innerHTML before shadowRoot creation.
   */
  override connectedCallback() {
    // we do this before calling super, to be sure we still have our innerHTML intact
    // note: we don't do it in constructor, because it would disable using document.createElement
    // as _buildResultRenderer needs the slot named result to already exists
    this.resultRenderer = this._buildResultRenderer();
    super.connectedCallback();
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-results': SearchaliciousResults;
  }
}
