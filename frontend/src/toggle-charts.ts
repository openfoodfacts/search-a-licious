import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {SearchaliciousEvents} from './utils/enums';
import {localized, msg} from '@lit/localize';

@customElement('toggle-charts')
@localized()
export class ToggleCharts extends LitElement {
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
  private toggleChartsSidebar() {
    this.dispatchEvent(
      new CustomEvent(SearchaliciousEvents.OPEN_CLOSE_CHART_SIDEBAR, {
        bubbles: true,
        composed: true,
      })
    );
  }

  override render() {
    return html`
      <button part="button" @click="${this.toggleChartsSidebar}">
        <span class="text">${msg('Show charts')}</span>
        <searchalicious-icon-chart size="12"></searchalicious-icon-chart>
      </button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'toggle-charts': ToggleCharts;
  }
}
