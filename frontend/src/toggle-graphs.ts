import {LitElement, html} from 'lit';
import {customElement} from 'lit/decorators.js';

@customElement('toggle-graphs')
export class ToggleGraphs extends LitElement {
  private toggleGraphs() {
    this.dispatchEvent(
      new CustomEvent('toggle-graphs', {
        bubbles: true,
        composed: true,
      })
    );
  }

  override render() {
    return html`
      <button part="button" @click="${this.toggleGraphs}">Show Graphs</button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'toggle-graphs': ToggleGraphs;
  }
}
