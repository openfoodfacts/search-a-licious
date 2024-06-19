import {LitElement, html} from 'lit';
import {customElement, property} from 'lit/decorators.js';

import {SearchaliciousResultCtlMixin} from './search-results-ctl';

import {SearchResultEvent} from './events';

// eslint-disable-next-line
declare const vega: any;

@customElement('searchalicious-chart')
export class SearchaliciousChart extends SearchaliciousResultCtlMixin(
  LitElement
) {
  // All these properties will change when vega logic
  // will be moved in API.
  // TODO: fail if some required properties are unset
  // (eg. key)
  @property()
  key?: string;

  @property()
  label?: string;

  @property({type: Array})
  categories: Array<string> = [];

  @property({attribute: false})
  // eslint-disable-next-line
  vegaRepresentation: any = undefined;

  override render() {
    try {
      vega;
    } catch (e) {
      if (e instanceof ReferenceError) {
        console.error(
          'Vega is required to use searchalicious-chart, you can import it using \
<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>'
        );
        return html`<p>Please install vega to use searchalicious-chart</p>`;
      }
      throw e;
    }

    if (this.vegaRepresentation === undefined) {
      return html`<p>no data</p>`;
    }
    return html`<div id="${this.key!}"></div>`;
  }

  // Computes the vega representation for given results
  // The logic will be partially moved in API in a following
  // PR.
  // Vega function assumes that rendered had been previously
  // called.
  override handleResults(event: SearchResultEvent) {
    if (event.detail.results.length === 0) {
      this.vegaRepresentation = undefined;
      return;
    }

    // Compute the distribution
    const values = Object.fromEntries(
      this.categories.map((category) => [category, 0])
    );

    for (const result of event.detail.results) {
      // We use ts-ignore here but it will be removed as soon as
      // vega logic will be moved in the api
      // @ts-ignore
      values[result[this.key]] += 1;
    }

    // Vega is used as a JSON visualization grammar
    // Doc: https://vega.github.io/vega/docs/
    // It would have been possible to use higher lever vega-lite API,
    // which is able to write vega specifications but it's probably too
    // much for our usage
    // Inspired by: https://vega.github.io/vega/examples/bar-chart/

    // I recommend to search on Internet for specific uses like:
    // * How to make vega responsive:
    // Solution: using signals and auto-size
    // https://gist.github.com/donghaoren/023b2246569e8f0615017507b473e55e
    // * How to hide vertical axis: do not add { scale: yscale, ...} in axes section

    this.vegaRepresentation = {
      $schema: 'https://vega.github.io/schema/vega/v5.json',
      title: this.label,
      // @ts-ignore
      // width: container.offsetWidth,
      autosize: {type: 'fit', contains: 'padding'},
      signals: [
        {
          name: 'width',
          init: 'containerSize()[0]',
          on: [{events: 'window:resize', update: 'containerSize()[0]'}],
        },
        {
          name: 'tooltip',
          value: {},
          on: [
            {events: 'rect:pointerover', update: 'datum'},
            {events: 'rect:pointerout', update: '{}'},
          ],
        },
      ],
      height: 140,
      padding: 5,
      data: [
        {
          name: 'table',
          values: Array.from(Object.entries(values), ([key, value]) => ({
            category: key,
            amount: value,
          })),
        },
      ],

      scales: [
        {
          name: 'xscale',
          type: 'band',
          domain: {data: 'table', field: 'category'},
          range: 'width',
          padding: 0.05,
          round: true,
        },
        {
          name: 'yscale',
          domain: {data: 'table', field: 'amount'},
          nice: true,
          range: 'height',
        },
      ],
      axes: [{orient: 'bottom', scale: 'xscale', domain: false, ticks: false}],
      marks: [
        {
          type: 'rect',
          from: {data: 'table'},
          encode: {
            enter: {
              x: {scale: 'xscale', field: 'category'},
              width: {scale: 'xscale', band: 1},
              y: {scale: 'yscale', field: 'amount'},
              y2: {scale: 'yscale', value: 0},
            },
            update: {
              fill: {value: 'steelblue'},
            },
            hover: {
              fill: {value: 'red'},
            },
          },
        },
        {
          type: 'text',
          encode: {
            enter: {
              align: {value: 'center'},
              baseline: {value: 'bottom'},
              fill: {value: '#333'},
            },
            update: {
              x: {scale: 'xscale', signal: 'tooltip.category', band: 0.5},
              y: {scale: 'yscale', signal: 'tooltip.amount', offset: -2},
              text: {signal: 'tooltip.amount'},
              fillOpacity: [{test: 'datum === tooltip', value: 0}, {value: 1}],
            },
          },
        },
      ],
    };
  }

  // vega rendering requires an html component with id == this.key
  // and consequently must be called AFTER render
  // Method updated is perfect for that
  // See lit.dev components lifecycle: https://lit.dev/docs/components/lifecycle/
  override updated() {
    if (this.vegaRepresentation === undefined) return;

    const container = this.renderRoot.querySelector(`#${this.key}`);

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
