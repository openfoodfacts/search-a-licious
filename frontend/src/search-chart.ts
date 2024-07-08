import {LitElement, html} from 'lit';
import {customElement, property} from 'lit/decorators.js';

import {WHITE_PANEL_STYLE} from './styles';
import {SearchResultDetail} from './signals';

import {SearchaliciousResultCtlMixin} from './mixins/search-results-ctl';

interface ChartSearchParamPOST {
  chart_type: string;
  field?: string;
  x?: string;
  y?: string;
}

export type ChartSearchParam = ChartSearchParamPOST | string;

// eslint raises error due to :any
// eslint-disable-next-line
declare const vega: any;

export class SearchaliciousChart extends SearchaliciousResultCtlMixin(
  LitElement
) {
  @property({attribute: false})
  vegaRepresentation: object | undefined = undefined;

  @property({attribute: false})
  vegaInstalled: boolean;

  static override styles = [WHITE_PANEL_STYLE];

  constructor() {
    super();
    this.vegaInstalled = this.testVegaInstalled();
  }

  override connectedCallback() {
    super.connectedCallback();

    this.searchResultDetailSignal.subscribe((searchResultDetail) => {
      this.updateCharts(searchResultDetail);
    });
  }

  /**
   * The name is used to get the right vega chart from
   * API search Result
   */
  getName(): string {
    throw new Error('Not implemented');
  }

  /**
   * Return the GET or POST param used for the API
   */
  getSearchParam(_isGetRequest: boolean): ChartSearchParam {
    throw new Error('Not implemented');
  }

  renderChart() {
    if (!this.vegaInstalled) {
      return html`<p>Please install vega to use searchalicious-chart</p>`;
    }

    if (this.vegaRepresentation === undefined) {
      return html`<slot class="white-panel" name="no-data"
        ><p>no data</p></slot
      >`;
    }

    return html`<div id="vega-container"></div>`;
  }

  override render() {
    return html` <div class="white-panel">${this.renderChart()}</div>`;
  }

  updateCharts(searchResultDetail: SearchResultDetail) {
    if (searchResultDetail.results.length === 0 || !this.vegaInstalled) {
      this.vegaRepresentation = undefined;
      return;
    }
    this.vegaRepresentation = searchResultDetail.charts[this.getName()];
  }

  testVegaInstalled() {
    try {
      vega;
      return true;
    } catch (e) {
      if (e instanceof ReferenceError) {
        console.error(
          'Vega is required to use searchalicious-chart, you can import it using \
<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>'
        );
        return false;
      }
      throw e;
    }
  }

  // vega rendering requires an html component with id == this.name
  // and consequently must be called AFTER render
  // Method updated is perfect for that
  // See lit.dev components lifecycle: https://lit.dev/docs/components/lifecycle/
  override updated() {
    if (this.vegaRepresentation === undefined) return;

    const container = this.renderRoot.querySelector(`#vega-container`);

    // How to display a vega chart: https://vega.github.io/vega/usage/#view
    const view = new vega.View(vega.parse(this.vegaRepresentation), {
      renderer: 'svg',
      container: container,
      hover: true,
    });
    view.runAsync();
  }
}

@customElement('searchalicious-distribution-chart')
export class SearchaliciousDistributionChart extends SearchaliciousChart {
  static override styles = [WHITE_PANEL_STYLE];

  // All these properties will change when vega logic
  // will be moved in API.
  @property()
  field = '';

  override getName() {
    return this.field;
  }

  override getSearchParam(isGetRequest: boolean) {
    if (isGetRequest) return this.field;
    else
      return {
        chart_type: 'DistributionChartType',
        field: this.field,
      };
  }
}
@customElement('searchalicious-scatter-chart')
export class SearchaliciousScatterChart extends SearchaliciousChart {
  static override styles = [WHITE_PANEL_STYLE];

  @property()
  x = '';

  @property()
  y = '';

  override getName() {
    return `${this.x}:${this.y}`;
  }

  override getSearchParam(isGetRequest: boolean) {
    if (isGetRequest) return `${this.x}:${this.y}`;
    else
      return {
        chart_type: 'ScatterChartType',
        x: this.x,
        y: this.y,
      };
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-distribution-chart': SearchaliciousDistributionChart;
    'searchalicious-scatter-chart': SearchaliciousScatterChart;
  }
}
