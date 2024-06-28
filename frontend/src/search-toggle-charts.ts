import {css, html, LitElement} from 'lit';
import {customElement} from 'lit/decorators.js';
import {ContextConsumer} from '@lit/context';
import {localized, msg} from '@lit/localize';
import {chartSideBarStateContext} from './context';
import {SearchaliciousEvents, SideBarState} from './utils/enums';

@customElement('searchalicious-toggle-charts')
@localized()
export class SearchaliciousToggleCharts extends LitElement {
  static override styles = css`
    button {
      display: flex;
      align-items: center;
      border-color: #cfac9e;
      border-radius: 1000px;
      padding: 0.4em 1em;
      border-style: solid;
      cursor: pointer;
      gap: 0.5rem;
    }
  `;

  /**
   * Context consumer for the sidebar state
   * It is provided by the app component
   * @private
   */
  private chartSideBarState = new ContextConsumer(this, {
    context: chartSideBarStateContext,
    subscribe: true,
  });

  /**
   * Toggle the charts sidebar
   * It dispatches an event to change the state of the sidebar to app component
   * @private
   */
  private toggleChartsSidebar() {
    const newState =
      this.chartSideBarState.value === SideBarState.CLOSED
        ? SideBarState.OPENED
        : SideBarState.CLOSED;

    this.dispatchEvent(
      new CustomEvent(SearchaliciousEvents.CHANGE_CHART_SIDEBAR_STATE, {
        bubbles: true,
        composed: true,
        detail: {
          state: newState,
        },
      })
    );
  }

  override render() {
    const text =
      this.chartSideBarState.value === SideBarState.CLOSED
        ? msg('Show charts')
        : msg('Hide charts');

    return html`
      <button part="button" @click="${this.toggleChartsSidebar}">
        <span class="text"> ${text} </span>
        <searchalicious-icon-chart size="12"></searchalicious-icon-chart>
      </button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-toggle-charts': SearchaliciousToggleCharts;
  }
}
