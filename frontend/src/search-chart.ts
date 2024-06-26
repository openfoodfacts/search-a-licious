import {LitElement} from 'lit';
import {customElement, property} from 'lit/decorators.js';

import {SearchaliciousResultCtlMixin} from './mixins/search-results-ctl';
import {SearchaliciousChartMixin} from './mixins/search-chart';

import {SearchResultEvent} from './events';

@customElement('searchalicious-distribution-chart')
export class SearchaliciousDistributionChart extends SearchaliciousResultCtlMixin(
  SearchaliciousChartMixin(LitElement)
) {
  @property()
  name = '';

  override getName() {
    return this.name;
  }

  // Vega function assumes that rendered had been previously
  // called.
  override handleResults(event: SearchResultEvent) {
    if (event.detail.results.length === 0 || !this.vegaInstalled) {
      this.vegaRepresentation = undefined;
      return;
    }

    // @ts-ignore
    this.vegaRepresentation = event.detail.charts[this.getName()];
  }
}
@customElement('searchalicious-scatter-chart')
export class SearchaliciousScatterChart extends SearchaliciousResultCtlMixin(
  SearchaliciousChartMixin(LitElement)
) {
  @property()
  x = '';

  @property()
  y = '';

  override getName() {
    return `${this.x}:${this.y}`;
  }

  // Vega function assumes that rendered had been previously
  // called.
  override handleResults(event: SearchResultEvent) {
    if (event.detail.results.length === 0 || !this.vegaInstalled) {
      this.vegaRepresentation = undefined;
      return;
    }
    // @ts-ignore
    this.vegaRepresentation = event.detail.charts[this.getName()];
    console.log(this.vegaRepresentation);
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-distribution-chart': SearchaliciousDistributionChart;
    'searchalicious-scatter-chart': SearchaliciousScatterChart;
  }
}
