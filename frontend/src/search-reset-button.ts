import {customElement, property} from 'lit/decorators.js';
import {localized, msg} from '@lit/localize';
import {html, LitElement, nothing} from 'lit';
import {SignalWatcher} from '@lit-labs/preact-signals';
import {canResetSearch} from './signals';
import {SearchaliciousEvents, SearchNameProperty} from './utils/enums';

/**
 * It is a transparent button that is used to reset the search.
 * It use the signal canResetSearch to know if it should be displayed.
 */
@customElement('searchalicious-reset-button')
@localized()
export class SearchaliciousResetButton extends SignalWatcher(LitElement) {
  @property({type: String, attribute: 'search-name'})
  searchName: SearchNameProperty = SearchNameProperty.SEARCHALICIOUS;

  dispatchResetSearchEvent() {
    this.dispatchEvent(
      new CustomEvent(SearchaliciousEvents.RESET_SEARCH, {
        bubbles: true,
        composed: true,
        detail: {searchName: this.searchName},
      })
    );
  }
  override render() {
    return html`
      ${canResetSearch(this.searchName).value
        ? html`
            <searchalicious-button-transparent
              @click=${this.dispatchResetSearchEvent}
            >
              <slot>${msg('Reset')}</slot>
            </searchalicious-button-transparent>
          `
        : nothing}
    `;
  }
}
declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-reset-button': SearchaliciousResetButton;
  }
}
