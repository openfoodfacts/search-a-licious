import {LitElement, html} from 'lit';
import {
  customElement,
  state,
  property,
  queryAssignedNodes,
} from 'lit/decorators.js';

import {SearchaliciousResultCtlMixin} from './search-results-ctl';

import {SearchResultEvent} from './events';
// @ts-ignore eslint-disable-next-line @typescript-eslint/ban-ts-comment  no-var
declare var vega: any;

interface ChartInfo {
  id: string;
  key: string;
  values: HistogramValues;
}

interface HistogramValues {
  [key: string]: number;
}

@customElement('searchalicious-charts')
export class SearchaliciousCharts extends SearchaliciousResultCtlMixin(
  LitElement
) {
  @state()
  @property()
  charts?: Array<ChartInfo>;

  @queryAssignedNodes({flatten: true})
  slotNodes!: Array<Node>;

  override render() {
    return html`<div><slot></slot></div>`;
  }

  _chartNodes(): SearchaliciousChart[] {
    return this.slotNodes.filter(
      (node) => node instanceof SearchaliciousChart
    ) as SearchaliciousChart[];
  }

  override handleResults(event: SearchResultEvent) {
    this._chartNodes().forEach((node) => {
      node.values = Object.fromEntries(
        node.categories.map((category) => [category, 0])
      );
    });

    for (const result of event.detail.results) {
      this._chartNodes().forEach((node) => {
        // @ts-ignore
        node.values[result[node.key]] += 1;
      });
    }
  }
}

@customElement('searchalicious-chart')
export class SearchaliciousChart extends LitElement {
  @property()
  // @ts-ignore
  key: string;

  @property()
  // @ts-ignore
  label: string;

  @property({type: Array})
  // @ts-ignore
  categories: Array<string>;

  @property({attribute: false})
  values?: any = [];

  override render() {
    const nbResults = Object.values(this.values).reduce(
      // @ts-ignore
      (prev, c) => c + prev,
      0
    );
    console.log(nbResults, this.values);
    // @ts-ignore
    const display = nbResults > 0 ? '' : 'display: none';
    return html`<div id="${this.key}" style="${display}"></div>`;
  }

  override updated() {
    const container = this.renderRoot.querySelector(`#${this.key}`);
    // Make vega responsive
    // https://gist.github.com/donghaoren/023b2246569e8f0615017507b473e55e

    const view = new vega.View(
      vega.parse({
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
            values: Array.from(Object.entries(this.values), ([key, value]) => ({
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

        axes: [
          {orient: 'bottom', scale: 'xscale', domain: false, ticks: false},
        ],
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
                fillOpacity: [
                  {test: 'datum === tooltip', value: 0},
                  {value: 1},
                ],
              },
            },
          },
        ],
      }),
      {
        renderer: 'svg',
        container: container,
        hover: true,
      }
    );
    view.runAsync();
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-charts': SearchaliciousCharts;
    'searchalicious-chart': SearchaliciousChart;
  }
}
