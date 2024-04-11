import {LitElement, html} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {SearchaliciousEvents} from './enums';

/**
 * An optional search button element.
 *
 * @slot - goes in button contents, default to "Search" string
 */
@customElement('searchalicious-button')
export class SearchaliciousButton extends LitElement {
  /**
   * the search we should trigger,
   * this corresponds to `name` attribute of corresponding search-bar
   */
  @property()
  search_name = 'searchalicious';

  override render() {
    return html`
      <button @click=${this._onClick}>
        <slot> Search </slot>
      </button>
    `;
  }

  private _onClick() {
    const detail = {search_name: this.search_name};
    // fire the search event
    const event = new CustomEvent(SearchaliciousEvents.LAUNCH_SEARCH, {
      bubbles: true,
      composed: true,
      detail: detail,
    });
    const success = this.dispatchEvent(event);
    console.log(success);
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-button': SearchaliciousButton;
  }
}
