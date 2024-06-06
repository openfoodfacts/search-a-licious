import {LitElement, html} from 'lit';
import {customElement, state} from 'lit/decorators.js';

import {SearchaliciousResultCtlMixin} from './search-results-ctl';
import {SearchResultEvent} from './events';

@customElement('searchalicious-charts')
export class SearchaliciousCharts extends SearchaliciousResultCtlMixin(
  LitElement
) {
  @state()
  nbResults = 0;

  override render() {
    return html`Nb results: ${this.nbResults} <--`;
  }

  override handleResults(event: SearchResultEvent) {
    this.nbResults = event.detail.results.length;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-charts': SearchaliciousCharts;
  }
}
