import {customElement} from 'lit/decorators.js';
import {css, html, LitElement} from 'lit';

@customElement('searchalicious-sidebar')
export class SearchaliciousSidebar extends LitElement {
  static override styles = css`
    .searchalicious-sidebar {
      background-color: var(--searchalicious-sidebar-background-color, #d1d1d1);
    }
  `;
  override render() {
    return html`
      <div class="searchalicious-sidebar">
        <slot></slot>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-sidebar': SearchaliciousSidebar;
  }
}
