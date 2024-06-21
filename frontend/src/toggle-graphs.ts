import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';

@customElement('toggle-graphs')
export class ToggleGraphs extends LitElement {
    static override styles = css`
        /* button {
            padding: 10px;
            background-color: #EFEFEF;
            color: black;
            border: none;
            cursor: pointer;
        } */
    `;

    private toggleGraphs() {
        this.dispatchEvent(new CustomEvent('toggle-graphs', {
            bubbles: true,
            composed: true
        }));
    }

    override render() {
        return html`
            <button part='button' @click="${this.toggleGraphs}">Toggle Graphs</button>
        `;
    }
}

declare global {
  interface HTMLElementTagNameMap {
    'toggle-graphs': ToggleGraphs;
  }
}
