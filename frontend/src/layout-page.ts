import {LitElement, html, css, nothing} from 'lit';
import {customElement, state} from 'lit/decorators.js';
import {classMap} from 'lit/directives/class-map.js';
import {SearchaliciousEvents} from './utils/enums';
import {EventRegistrationMixin} from './event-listener-setup';

/**
 * Component for the layout of the page
 * Three columns layout with display flex
 */
@customElement('layout-page')
export class LayoutPage extends EventRegistrationMixin(LitElement) {
  static override styles = css`
    .row {
      display: grid;
      grid-template-columns: 20% 1fr;
      box-sizing: border-box;
      max-width: 100%;
    }
    .row.display-graphs {
      grid-template-columns: 20% 1fr 20%;
    }
    .row.display-graphs.is-expanded {
      grid-template-columns: 20% 1fr 30%;
    }

    .col-1,
    .col-3 {
      height: 100%;
      background-color: #d1d1d1;
      border: 1px solid #cccccc;
      //background-color: rgba(0, 0, 0, 20%);
    }
    .col-2 {
      flex-grow: 1;
    }
    .column {
      padding: 1rem;
    }
  `;

  /**
   * Display graphs or not
   */
  @state()
  isGraphSidebarOpened = false;

  /**
   * Expand the graph sidebar
   */
  @state()
  isGraphSidebarExpanded = false;

  private _toggleIsGraphSidebarOpened() {
    this.isGraphSidebarOpened = !this.isGraphSidebarOpened;
    if (!this.isGraphSidebarOpened) {
      this.isGraphSidebarExpanded = false;
    }
  }

  private _toggleIsGraphSidebarExpanded() {
    this.isGraphSidebarExpanded = !this.isGraphSidebarExpanded;
  }

  override connectedCallback() {
    super.connectedCallback();

    window.addEventListener(SearchaliciousEvents.OPEN_CLOSE_GRAPH_SIDEBAR, () =>
      this._toggleIsGraphSidebarOpened()
    );
    window.addEventListener(
      SearchaliciousEvents.REDUCE_EXPAND_GRAPH_SIDEBAR,
      () => this._toggleIsGraphSidebarExpanded()
    );
  }

  override disconnectedCallback() {
    window.removeEventListener(
      SearchaliciousEvents.OPEN_CLOSE_GRAPH_SIDEBAR,
      this._toggleIsGraphSidebarOpened
    );
    window.removeEventListener(
      SearchaliciousEvents.OPEN_CLOSE_GRAPH_SIDEBAR,
      this._toggleIsGraphSidebarExpanded
    );
    super.disconnectedCallback();
  }

  override render() {
    const rowClass = {
      'display-graphs': this.isGraphSidebarOpened,
      'is-expanded': this.isGraphSidebarExpanded,
    };
    return html`
      <div class="row ${classMap(rowClass)}">
        <div class="column col-1">
          <slot name="col-1"></slot>
        </div>
        <div class="column col-2">
          <slot name="col-2-header"></slot>
          <slot name="col-2"></slot>
        </div>
        ${this.isGraphSidebarOpened
          ? html`
              <div class="column col-3">
                <slot name="col-3"></slot>
              </div>
            `
          : nothing}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'layout-page': LayoutPage;
  }
}
