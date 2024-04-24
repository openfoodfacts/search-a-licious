import {LitElement, html} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {BaseSearchDetail, LaunchSearchEvent} from './events';
import {SearchaliciousEvents} from './enums';

/**
 * An optional search button element that launch the search.
 *
 * @slot - goes in button contents, default to "Search" string
 */
@customElement('searchalicious-button')
export class SearchaliciousButton extends LitElement {
  /**
   * the search we should trigger,
   * this corresponds to `name` attribute of corresponding search-bar
   */
  @property({attribute: 'search-name'})
  searchName = 'searchalicious';

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
  _launchSearch() {
    const detail: BaseSearchDetail = {searchName: this.searchName};
    // fire the search event
    const event = new CustomEvent(SearchaliciousEvents.LAUNCH_SEARCH, {
      bubbles: true,
      composed: true,
      detail: detail,
    }) as LaunchSearchEvent;
    this.dispatchEvent(event);
  }

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
