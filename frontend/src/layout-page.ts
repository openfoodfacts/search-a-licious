import {LitElement, html, css} from 'lit';
import {customElement, state, queryAssignedNodes} from 'lit/decorators.js';
import {classMap} from 'lit/directives/class-map.js';
import {SearchaliciousEvents} from './utils/enums';
import {EventRegistrationMixin} from './event-listener-setup';
import {HIDE_STYLE} from './styles';

/**
 * Component for the layout of the page
 * Three columns layout with display flex
 */
@customElement('layout-page')
export class LayoutPage extends EventRegistrationMixin(LitElement) {
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
   * Display charts or not
   */
  @state()
  isChartSidebarOpened = false;

  /**
   * Expand the chart sidebar
   */
  @state()
  isChartSidebarExpanded = false;

  /**
   * Slot nodes
   */
  @queryAssignedNodes({slot: 'col-3', flatten: true})
  slotNodes!: Array<Node>;

  private _getAllCharts() {
    return (this.slotNodes[0] as HTMLElement).querySelectorAll(
      'searchalicious-chart'
    );
  }
  private _toggleIsChartSidebarOpened() {
    this.isChartSidebarOpened = !this.isChartSidebarOpened;
    if (!this.isChartSidebarOpened) {
      this.isChartSidebarExpanded = false;
    } else {
      // Force all charts to update their size
      this._getAllCharts().forEach((chart) => chart.requestUpdate());
    }
  }

  private _toggleIsChartSidebarExpanded() {
    this.isChartSidebarExpanded = !this.isChartSidebarExpanded;
  }

  override connectedCallback() {
    super.connectedCallback();

    window.addEventListener(SearchaliciousEvents.OPEN_CLOSE_CHART_SIDEBAR, () =>
      this._toggleIsChartSidebarOpened()
    );
    window.addEventListener(
      SearchaliciousEvents.REDUCE_EXPAND_CHART_SIDEBAR,
      () => this._toggleIsChartSidebarExpanded()
    );
  }

  override disconnectedCallback() {
    window.removeEventListener(
      SearchaliciousEvents.OPEN_CLOSE_CHART_SIDEBAR,
      this._toggleIsChartSidebarOpened
    );
    window.removeEventListener(
      SearchaliciousEvents.OPEN_CLOSE_CHART_SIDEBAR,
      this._toggleIsChartSidebarExpanded
    );
    super.disconnectedCallback();
  }

  override render() {
    const rowClass = {
      'display-charts': this.isChartSidebarOpened,
      'is-expanded': this.isChartSidebarExpanded,
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
            hidden: !this.isChartSidebarOpened,
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
    'layout-page': LayoutPage;
  }
}
