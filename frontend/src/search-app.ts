import {html, LitElement} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {chartSideBarStateContext} from './context';
import {SearchaliciousEvents, SideBarState} from './utils/enums';
import {provide} from '@lit/context';
import {EventRegistrationMixin} from './event-listener-setup';

@customElement('searchalicious-app')
export class SearchaliciousApp extends EventRegistrationMixin(LitElement) {
  /**
   * State of the chart sidebar
   * Each LitElement that needs to know the state of the sidebar should consume this context
   * By default, the chart sidebar is opened
   */
  @provide({context: chartSideBarStateContext})
  @property({attribute: false})
  chartSideBarState = SideBarState.CLOSED;

  override connectedCallback() {
    super.connectedCallback();

    // Listen to the event that changes the state of the sidebar
    this.addEventHandler(
      SearchaliciousEvents.CHANGE_CHART_SIDEBAR_STATE,
      (event: Event) => {
        this.chartSideBarState = (event as CustomEvent).detail.state;
      }
    );
  }

  override disconnectedCallback() {
    super.disconnectedCallback();
    this.removeEventHandler(
      SearchaliciousEvents.CHANGE_CHART_SIDEBAR_STATE,
      (event: Event) => {
        this.chartSideBarState = (event as CustomEvent).detail.state;
      }
    );
  }

  override render() {
    return html`
      <div>
        <slot></slot>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-app': SearchaliciousApp;
  }
}
