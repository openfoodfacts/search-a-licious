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
    // the number of results
    resultCounter: number = 0;

    override connectedCallback() {
        super.connectedCallback();
        // listen for the search-results-updated event
        window.addEventListener('search-results-updated', this.handleSearchResultsUpdated as EventListener);
    }

    override disconnectedCallback() {
        // stop listening for the search-results-updated event
        window.removeEventListener('search-results-updated', this.handleSearchResultsUpdated as EventListener);
        super.disconnectedCallback();
    }

    handleSearchResultsUpdated(event: CustomEvent) {
        console.log('ResultsCounterDisplay: search-results-updated event received');
        // update the counter
        this.resultCounter = event.detail.count;
        console.log('ResultsCounterDisplay: count =', this.resultCounter);
    }

    override render() {
        return html`<div>${this.resultCounter} results found</div>`;
    }
}