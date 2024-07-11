import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {msg} from '@lit/localize';
import {SearchaliciousResultCtlMixin} from './mixins/search-results-ctl';
@customElement('searchalicious-count')
export class SearchCount extends SearchaliciousResultCtlMixin(LitElement) {
  static override styles = css`
    :host {
      display: block;
      padding: 5px;
      color: var(--searchalicious-count-color, inherit);
    }
  `;

  @property({attribute: 'display-time', type: Boolean})
  displayTime = false;

  // HTML to display before the search is launched
  beforeSearch = html``;

  // HTML to display when there are no results
  get noResults() {
    return html`<div>${msg('No results found')}</div>`;
  }

  renderResultsFound() {
    let result;
    if (this.searchResultDetail.isCountExact) {
      result = `${this.searchResultDetail.count} ${msg('results found')}`;
    } else {
      result = msg(
        html`More than ${this.searchResultDetail.count} results found`
      );
    }

    if (this.displayTime) {
      result = html`${result}
        <span part="result-display-time">
          (${this.searchResultDetail.displayTime}ms)</span
        >`;
    }

    return result;
  }

  /**
   * Render the component
   */
  override render() {
    if (this.searchResultDetail.count > 0) {
      return html`<div part="result-found">${this.renderResultsFound()}</div>`;
    } else if (this.searchResultDetail.isSearchLaunch) {
      return html`<slot name="no-results">${this.noResults}</slot>`;
    } else {
      return html`<slot name="before-search">${this.beforeSearch}</slot>`;
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-count': SearchCount;
  }
}
