import {LitElement, html} from 'lit';
import {customElement, property} from 'lit/decorators.js';

import {WHITE_PANEL_STYLE} from './styles';
import {SearchResultDetail} from './signals';
import {SearchaliciousResultCtlMixin} from './mixins/search-results-ctl';

// eslint-disable-next-line
declare const vega: any;

@customElement('searchalicious-chart')
export class SearchaliciousChart extends SearchaliciousResultCtlMixin(
  LitElement
) {
  static override styles = [WHITE_PANEL_STYLE];

  // All these properties will change when vega logic
  // will be moved in API.
  @property()
  name = '';

  @property({attribute: false})
  // eslint-disable-next-line
  vegaRepresentation: any = undefined;

  @property({attribute: false})
  vegaInstalled: boolean;

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

  getName() {
    return this.name;
  }

  renderChart() {
    if (!this.vegaInstalled) {
      return html`<p>Please install vega to use searchalicious-chart</p>`;
    }

    if (this.vegaRepresentation === undefined) {
      return html`<slot name="no-data"><p>no data</p></slot>`;
    }

    return html`<div id="${this.name!}"></div>`;
  }

  override render() {
    return html` <div class="white-panel">${this.renderChart()}</div>`;
  }

  updateCharts(searchResultDetail: SearchResultDetail) {
    if (searchResultDetail.results.length === 0 || !this.vegaInstalled) {
      this.vegaRepresentation = undefined;
      return;
    }

    // @ts-ignore
    this.vegaRepresentation = searchResultDetail.charts[this.name!];
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

    const container = this.renderRoot.querySelector(`#${this.name}`);

    // How to display a vega chart: https://vega.github.io/vega/usage/#view
    const view = new vega.View(vega.parse(this.vegaRepresentation), {
      renderer: 'svg',
      container: container,
      hover: true,
    });
    view.runAsync();
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-chart': SearchaliciousChart;
  }
}
