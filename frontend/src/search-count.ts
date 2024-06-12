import {LitElement, html, css} from 'lit';
import {customElement, state} from 'lit/decorators.js';
import {SearchResultEvent} from './events';
import {
  SearchaliciousResultCtlMixin,
  SearchaliciousResultsCtlInterface,
} from './mixins/search-results-ctl';

@customElement('searchalicious-count')
export class ResultsCounterDisplay
  extends SearchaliciousResultCtlMixin(LitElement)
  implements SearchaliciousResultsCtlInterface
{
  static override styles = css`
    :host {
      display: block;
      padding: 5px;
      color: white;
    }
  `;

  // the last number of results found
  @state()
  nbResults: number = 0;

  // HTML to display before the search is launched
  beforeSearch = html``;

  // HTML to display when there are no results
  noResults = html`<div>No results found</div>`;

  /**
   * Render the component
   */
  override render() {
    if (this.nbResults > 0) {
      return this.nbResults + ' results found';
    } else if (this.searchLaunched) {
      return html`<slot name="no-results">${this.noResults}</slot>`;
    } else {
      return html`<slot name="before-search">${this.beforeSearch}</slot>`;
    }
  }

  /**
   * Handle the search result event
   */
  override handleResults(event: SearchResultEvent) {
    this.nbResults = event.detail.count; // it's reactive so it will trigger a render
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-count': ResultsCounterDisplay;
  }
}
