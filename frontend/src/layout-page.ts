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
        flex-basis: 20%;
        }
        .col-2 {
        flex-basis: 50%;
        }
        .col-3 {
        flex-basis: 30%;
        }
        .col-1-no-graph {
            flex-basis: 20%;
        }
        .col-2-no-graph {
            flex-basis: 80%;
        }
    `;

    /**
     * Display graphs or not
     */
    @state()
    displayGraphs = false;

    override connectedCallback() {
        super.connectedCallback();
        window.addEventListener('toggle-graphs', (event: Event) => this.toggleGraphs(event));
    }

    override disconnectedCallback() {
        window.removeEventListener('toggle-graphs', (event: Event) => this.toggleGraphs(event));
        super.disconnectedCallback();
    }

    private toggleGraphs(_: Event) {
        this.displayGraphs = !this.displayGraphs; 
    }
    
    override render() {
        return html`
        <div class="column ${ this.displayGraphs ? 'col-1' : 'col-1-no-graph' }"><slot name="col-1"></slot></div>
        <div class="column ${ this.displayGraphs ? 'col-2' : 'col-2-no-graph' }"><slot name="col-2"></slot></div>
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
