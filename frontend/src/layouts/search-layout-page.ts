import {css, html, LitElement} from 'lit';
import {customElement, queryAssignedNodes} from 'lit/decorators.js';
import {classMap} from 'lit/directives/class-map.js';
import {SideBarState} from '../utils/enums';
import {EventRegistrationMixin} from '../event-listener-setup';
import {HIDE_STYLE} from '../styles';
import {ContextConsumer} from '@lit/context';
import {chartSideBarStateContext} from '../context';
import {SearchaliciousResultCtlMixin} from '../mixins/search-results-ctl';

/**
 * Component for the layout of the page
 * Three columns layout with display flex
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
        this._refreshCharts();
      }
    },
  });

  /**
   * Slot nodes
   */
  @queryAssignedNodes({slot: 'col-3', flatten: true})
  slotNodes!: Array<Node>;

  /**
   * Refresh vega charts by dispatching a resize event
   * This is needed because vega charts are not displayed correctly because of the hidden sidebar
   * @private
   */
  private _refreshCharts() {
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
    }, 0);
  }

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
          <slot name="col-3"></slot>
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
