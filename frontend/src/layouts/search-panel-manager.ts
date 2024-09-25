import {html, LitElement} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {chartSideBarStateContext} from '../context';
import {SearchaliciousEvents, SideBarState} from '../utils/enums';
import {provide} from '@lit/context';
import {EventRegistrationMixin} from '../event-listener-setup';

/**
 * This component enables sharing state about panels in a central place.
 *
 * it should be high in the hierarchy (just below `body`)
 * to wrap all other web-components
 *
 * It must be used if you want to use the `searchalicious-layout-page` component
 *
 * It allows to have a global variable to store with @lit/context
 */
@customElement('searchalicious-panel-manager')
export class SearchaliciousPanelManager extends EventRegistrationMixin(
  LitElement
) {
  /**
   * State of the chart sidebar
   * Each LitElement that needs to know the state of the sidebar should consume this context
   * By default, the chart sidebar is opened
   */
  @provide({context: chartSideBarStateContext})
  @property({type: String, attribute: 'chart-sidebar-state'})
  chartSideBarState = SideBarState.OPENED;

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
    'searchalicious-panel-manager': SearchaliciousPanelManager;
  }
}
