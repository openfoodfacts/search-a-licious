import {customElement} from 'lit/decorators.js';
import {localized, msg} from '@lit/localize';
import {html, LitElement, nothing} from 'lit';
import {SignalWatcher} from '@lit-labs/preact-signals';
import {canResetSearch} from './signals';
import {SearchaliciousEvents} from './utils/enums';

/**
 * It is a transparent button that is used to reset the search.
 * It just exists to have translated text "Reset" in it.
 */
@customElement('searchalicious-reset-button')
@localized()
export class SearchaliciousResetButton extends SignalWatcher(LitElement) {
  dispatchResetSearchEvent() {
    this.dispatchEvent(
      new CustomEvent(SearchaliciousEvents.RESET_SEARCH, {
        bubbles: true,
        composed: true,
      })
    );
  }
  override render() {
    return html`
      ${canResetSearch.value
        ? html`
            <searchalicious-button-transparent
              @click=${this.dispatchResetSearchEvent}
              >${msg('Reset')}
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
