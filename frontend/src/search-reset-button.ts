import {customElement} from 'lit/decorators.js';
import {localized, msg} from '@lit/localize';
import {html, LitElement} from 'lit';

/**
 * It is a transparent button that is used to reset the search.
 * It just exists to have translated text "Reset" in it.
 */
@customElement('searchalicious-reset-button')
@localized()
export class SearchaliciousResetButton extends LitElement {
  override render() {
    return html`
      <searchalicious-button-transparent>
        ${msg('Reset')}
      </searchalicious-button-transparent>
    `;
  }
}
declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-reset-button': SearchaliciousResetButton;
  }
}
