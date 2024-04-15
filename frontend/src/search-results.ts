import {LitElement, html} from 'lit';
import {customElement, property, state} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';

import {EventRegistrationMixin} from './event-listener-setup';
import {SearchResultEvent} from './events';
import {SearchaliciousEvents} from './enums';
/**
 * The search results element
 *
 * It will display results based upon the InnerHTML considered as a template.
 *
 * It reacts to the `searchalicious-result` event fired by the search controller
 */
@customElement('searchalicious-results')
export class SearchaliciousResults extends EventRegistrationMixin(LitElement) {
  /**
   * the search we display result for,
   * this corresponds to `name` attribute of corresponding search-bar
   */
  @property({attribute: 'search-name'})
  searchName = 'searchalicious';

  // the search results
  @state()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  results: Record<string, any>[] = [];

  // attribute giving id
  @property({attribute: 'result-id'})
  resultId = 'id';

  /**
   * Get the slot contents and interpret it as a JS template.
   */
  getResultTemplate() {
    return (
      this.renderRoot.querySelector('slot')?.toString() ||
      'Please provide a template'
    );
  }

  override render() {
    const resultTemplate = this.getResultTemplate();
    console.log('Result template');
    console.dir(resultTemplate);
    return html` <ul part="results">
      ${repeat(
        this.results,
        (item) => item[this.resultId] as string,
        (item, index) => html` <li part="result">Result ${index} ${item}</li>`
      )}
    </ul>`;
  }

  _displayResults(event: Event) {
    // check if event is for our search
    const detail = (event as SearchResultEvent).detail;
    if (detail.searchName === this.searchName) {
      this.results = detail.results; // it's reactive, should trigger rendering
    }
  }

  // connect to our specific events
  override connectedCallback() {
    super.connectedCallback();
    this.addEventHandler(SearchaliciousEvents.NEW_RESULT, (event) =>
      this._displayResults(event)
    );
  }
  // connect to our specific events
  override disconnectedCallback() {
    super.disconnectedCallback();
    this.removeEventHandler(SearchaliciousEvents.NEW_RESULT, (event) =>
      this._displayResults(event)
    );
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-results': SearchaliciousResults;
  }
}
