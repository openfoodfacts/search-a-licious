import {LitElement, html} from 'lit';
import {customElement, state} from 'lit/decorators.js';

import {SearchaliciousResultCtlMixin} from './search-results-ctl';

import {SearchResultEvent} from './events';
// @ts-ignore eslint-disable-next-line @typescript-eslint/ban-ts-comment  no-var
declare var vega: any;

@customElement('searchalicious-@ts-ignorecharts')
export class SearchaliciousCharts extends SearchaliciousResultCtlMixin(
  LitElement
) {
  @state()
  nbResults = 0;

  override render() {
    return html`<p>hello world</p>
      <div id="pigeon"></div>`;
  }

  override handleResults(event: SearchResultEvent) {
    this.nbResults = event.detail.results.length;
    const container = this.renderRoot.querySelector('#pigeon');

    const view = new vega.View(
      vega.parse({
        $schema: 'https://vega.github.io/schema/vega/v5.json',
        description:
          'A basic bar chart example, with value labels shown upon pointer hover.',
        width: 400,
        height: 200,
        padding: 5,

        data: [
          {
            name: 'table',
            values: [
              {category: 'A', amount: 28},
              {category: 'B', amount: 55},
              {category: 'C', amount: 43},
              {category: 'D', amount: 91},
              {category: 'E', amount: 81},
              {category: 'F', amount: 53},
              {category: 'G', amount: 19},
              {category: 'H', amount: 87},
            ],
          },
        ],
        signals: [
          {
            name: 'tooltip',
            value: {},
            on: [
              {events: 'rect:pointerover', update: 'datum'},
              {events: 'rect:pointerout', update: '{}'},
            ],
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
          {orient: 'bottom', scale: 'xscale'},
          {orient: 'left', scale: 'yscale'},
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
  }
}
