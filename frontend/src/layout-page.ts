import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';

/**
 * Component for the layout of the page
 * Three columns layout with display flex
 */
@customElement('layout-page')
export class LayoutPage extends LitElement {
    static override styles = css`
        :host {
        display: flex;
        flex-direction: row;
        gap: 20px;
        }
        .column {
        flex: 1;
        }
        .col-1 {
        flex-basis: 10%;
        }
        .col-2 {
        flex-basis: 50%;
        }
        .col-3 {
        flex-basis: 30%;
        }
    `;

    /**
     * Display graphs or not
     */
    @state()
    displayGraphs = false;
    
    override render() {
        return html`
        <div class="column col-1"><slot name="col-1"></slot></div>
        <div class="column col-2"><slot name="col-2"></slot></div>
        ${this.displayGraphs ?
            html`<div class="column col-3"><slot name="col-3"></slot></div>` :
            ''
        }
        `;
    }
}

declare global {
  interface HTMLElementTagNameMap {
    'layout-page': LayoutPage;
  }
}
