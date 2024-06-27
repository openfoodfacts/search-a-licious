import {customElement, property} from 'lit/decorators.js';
import {html, LitElement} from 'lit';
import {iconStyle} from '../css';

/**
 * A custom element that represents a search icon.
 * It is used to represent the search icon in the search bar.
 */
@customElement('searchalicious-icon-chart')
export class SearchaliciousIconChart extends LitElement {
  static override styles = [iconStyle];

  @property({type: Number})
  size = 16;

  override render() {
    return html`
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 16 16"
        width=${this.size}
        height=${this.size}
        preserveAspectRatio="xMidYMid meet"
        part="icon"
      >
        <rect x="2" y="8" width="3" height="8" fill="#000000" />
        <rect x="7" y="4" width="3" height="12" fill="#000000" />
        <rect x="12" y="6" width="3" height="10" fill="#000000" />
      </svg>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-icon-char': SearchaliciousIconChart;
  }
}
