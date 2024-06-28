import {LitElement, html} from 'lit';
import {property} from 'lit/decorators.js';

import {Constructor} from './utils';

// eslint-disable-next-line
declare const vega: any;

interface ChartSearchParamPOST {
  chart_type: string,
  field?: string,
  x?: string,
  y?: string
}

export type ChartSearchParam = ChartSearchParamPOST | string;


export interface SearchaliciousChartInterface extends LitElement {
  vegaInstalled: Boolean;

  // eslint-disable-next-line
  vegaRepresentation: any;

  testVegaInstalled(): void;
  getName(): string;
}

export const SearchaliciousChartMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  class SearchaliciousChartMixinclass extends superClass {
    @property({attribute: false})
    // eslint-disable-next-line
    vegaRepresentation: any = undefined;

    @property({attribute: false})
    vegaInstalled: boolean;

    // eslint-disable-next-line
    constructor(...args: any[]) {
      super(args);
      this.vegaInstalled = this.testVegaInstalled();
    }

    /**
     * Return the GET or POST param used for the API
     */
    getSearchParam(_isGetRequest: boolean): ChartSearchParam {
      throw new Error('Not implemented')
    }

    /**
     * The name is used to get the right vega chart from
     * API search Result
     */
    getName(): string {
      throw new Error('Not implemented')
    }

    override render() {
      if (!this.vegaInstalled) {
        return html`<p>Please install vega to use searchalicious-chart</p>`;
      }

      if (this.vegaRepresentation === undefined) {
        return html`<slot class="white-panel" name="no-data"
          ><p>no data</p></slot
        >`;
      }

      return html`<div class="white-panel" id="vega-container"></div>`;
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

  return SearchaliciousChartMixinclass as Constructor<SearchaliciousChartInterface> &
    T;
};
