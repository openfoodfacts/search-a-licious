import {LitElement, html} from 'lit';
import {customElement} from 'lit/decorators.js';
import {SearchActionMixin} from './mixins/search-action';

/**
 * An optional search button element that launch the search.
 *
 * @slot - goes in button contents, default to "Search" string
 */
@customElement('searchalicious-button')
export class SearchaliciousButton extends SearchActionMixin(LitElement) {
  /**
   * the search we should trigger,
   * this corresponds to `name` attribute of corresponding search-bar
   */

  override render() {
    return html`
      <button
        @click=${this._onClick}
        @keyup=${this._onKeyUp}
        part="button"
        role="button"
      >
        <slot> Search </slot>
      </button>
    `;
  }

  /**
   * Launch search by emitting the LAUNCH_SEARCH signal
   */
  private _onClick() {
    this._launchSearch();
  }

  private _onKeyUp(event: Event) {
    const kbd_event = event as KeyboardEvent;
    if (kbd_event.key === 'Enter') {
      this._launchSearch();
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-button': SearchaliciousButton;
  }
}
