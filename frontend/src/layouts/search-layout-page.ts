import {css, html, LitElement} from 'lit';
import {customElement, queryAssignedNodes} from 'lit/decorators.js';
import {classMap} from 'lit/directives/class-map.js';
import {SideBarState} from '../utils/enums';
import {EventRegistrationMixin} from '../event-listener-setup';
import {HIDE_STYLE} from '../styles';
import {ContextConsumer} from '@lit/context';
import {chartSideBarStateContext} from '../context';
import {SearchaliciousResultCtlMixin} from '../mixins/search-results-ctl';
import {refreshCharts} from '../utils/charts';

/**
 * Component for the layout of the page
 *
 * It allows to handle sidebars:
 * Three columns layout with display flex,
 * one for facets, one for the results and one for the chart sidebar
 */
@customElement('searchalicious-layout-page')
export class SearchLayoutPage extends SearchaliciousResultCtlMixin(
  EventRegistrationMixin(LitElement)
) {
  static override styles = [
    HIDE_STYLE,
    css`
      .row {
        display: grid;
        grid-template-columns: 20% 1fr;
        box-sizing: border-box;
        max-width: 100%;
      }
      .row.display-charts {
        grid-template-columns: 20% 1fr 20%;
      }
      .row.display-charts.is-expanded {
        grid-template-columns: 20% 1fr 30%;
      }

      .col-1,
      .col-3 {
        height: 100%;
        background-color: #f2e9e4;
        border: 1px solid #cccccc;
      }
      .col-2 {
        flex-grow: 1;
      }
      .column {
        padding: 1rem;
      }

      @media (max-width: 800px) {
        .row {
          grid-template-columns: 1fr;
        }
      }
    `,
  ];

  /**
   * Context consumer for the sidebar state
   * This is used to open and close the sidebar
   * @private
   */
  private chartSideBarState = new ContextConsumer(this, {
    context: chartSideBarStateContext,
    subscribe: true,
    callback: (state: SideBarState) => {
      if (state !== SideBarState.CLOSED) {
        // Refresh the charts when the sidebar is opened
        // if we don't do this, the charts will not be displayed correctly
        refreshCharts();
      }
    },
  });

  override connectedCallback() {
    super.connectedCallback();
    // Refresh the charts when the search result detail is updated
    this.searchResultDetailSignal.subscribe(() => {
      refreshCharts();
    });
  }

  /**
   * Slot nodes
   */
  @queryAssignedNodes({slot: 'col-3', flatten: true})
  slotNodes!: Array<Node>;

  override render() {
    const rowClass = {
      'display-charts': this.chartSideBarState.value !== SideBarState.CLOSED,
      'is-expanded': this.chartSideBarState.value === SideBarState.EXPANDED,
    };
    return html`
      <div class="row ${classMap(rowClass)}">
        <div class="column col-1">
          <slot name="col-1"></slot>
        </div>
        <div class="column col-2">
          <slot name="col-2"></slot>
        </div>

        <div
          class="column col-3 ${classMap({
            hidden: this.chartSideBarState.value === SideBarState.CLOSED,
          })}"
        >
          <div
            class="${classMap({
              hidden: !this.searchResultDetail.isSearchLaunch,
            })}"
          >
            <slot name="col-3"></slot>
          </div>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious--layout-page': SearchLayoutPage;
  }
}
