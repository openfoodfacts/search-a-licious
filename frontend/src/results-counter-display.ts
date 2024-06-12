import { LitElement, html } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { SearchResultEvent } from './events';
import { SearchaliciousResultCtlMixin, SearchaliciousResultsCtlInterface } from './search-results-ctl';

@customElement('results-counter-display')
export class ResultsCounterDisplay extends SearchaliciousResultCtlMixin(LitElement) implements SearchaliciousResultsCtlInterface {
    // the last number of results found
    @state()
    nbResults: number = 0;

    override render() {
        return html`<div>${this.nbResults} results found</div>`;
    }

    /**
     * Handle the search result event
     */
    override handleResults(event: SearchResultEvent) {
        console.log('ResultsCounterDisplay.handleResults', event.detail);
        this.nbResults = event.detail.count; // it's reactive so it will trigger a render
    }

    override connectedCallback(): void {
        console.log('ResultsCounterDisplay.connectedCallback');
        super.connectedCallback();
    }

    override disconnectedCallback(): void {
        super.disconnectedCallback();
    }
}