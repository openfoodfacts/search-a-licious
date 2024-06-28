import {LitElement} from 'lit';
import {customElement, property} from 'lit/decorators.js';

import {
  SearchaliciousChartMixin,
  SearchaliciousChartResultCtlMixin,
} from './mixins/search-chart';

import {SearchResultEvent} from './events';

import {WHITE_PANEL_STYLE} from './styles';

@customElement('searchalicious-distribution-chart')
export class SearchaliciousDistributionChart extends SearchaliciousChartResultCtlMixin(
  SearchaliciousChartMixin(LitElement)
) {
  static override styles = [WHITE_PANEL_STYLE];

  // All these properties will change when vega logic
  // will be moved in API.
  @property()
  field = '';

  override getName() {
    return this.field;
  }

  getSearchParam(isGetRequest: boolean) {
    if (isGetRequest) return this.field;
    else
      return {
        chart_type: 'DistributionChartType',
        field: this.field,
      };
  }
}
@customElement('searchalicious-scatter-chart')
export class SearchaliciousScatterChart extends SearchaliciousChartResultCtlMixin(
  SearchaliciousChartMixin(LitElement)
) {
  static override styles = [WHITE_PANEL_STYLE];

  @property()
  x = '';

  @property()
  y = '';

  override getName() {
    return `${this.x}:${this.y}`;
  }

  getSearchParam(isGetRequest: boolean) {
      if (isGetRequest)
        return `${this.x}:${this.y}`;
      else
        return {
          chart_type: 'ScatterChartType',
          x: this.x,
          y: this.y
        };
  }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-distribution-chart': SearchaliciousDistributionChart;
    'searchalicious-scatter-chart': SearchaliciousScatterChart;
  }
}
