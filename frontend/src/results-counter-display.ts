import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';

/**
 * The results counter display
 *
 * It will display the number of results found
 */
@customElement('results-counter-display')
export class ResultsCounterDisplay extends LitElement {
    static override styles = css`
        div {
        color: white;
        }
    `;

    @state()
    count: number = 0;

    override connectedCallback() {
        super.connectedCallback();
        console.log('ResultsCounterDisplay: connected');
        this.addEventListener('search-results-updated', this.handleSearchResultsUpdated as EventListener);
    }

    override disconnectedCallback() {
        this.removeEventListener('search-results-updated', this.handleSearchResultsUpdated as EventListener);
        console.log('ResultsCounterDisplay: disconnected');
        super.disconnectedCallback();
    }

    handleSearchResultsUpdated(event: CustomEvent) {
        console.log('ResultsCounterDisplay: search-results-updated event received');
        const detail = event.detail.count
        console.log('ResultsCounterDisplay: search-results-updated', detail);
        this.count = detail;
    }

    override render() {
        return html`<div>${this.count} results found</div>`;
    }
}