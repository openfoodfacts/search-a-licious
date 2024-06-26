import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {searchBarInputAndButtonStyle} from './css/header';
import {BasicEvents} from './utils/enums';

/**
 * An optional search button element that launch the search.
 *
 * @slot - goes in button contents, default to "Search" string
 */
@customElement('searchalicious-button')
export class SearchaliciousButton extends LitElement {
  static override styles = [
    searchBarInputAndButtonStyle,
    css`
      button {
        background-color: var(--search-button-background-color, #341100);
        border-radius: 0px 1000px 1000px 0px;
        padding: 0.4rem 0.5rem;
        margin: 0;
        border: 0;
        z-index: 2;
        cursor: pointer;
      }
    `,
  ];

  /**
   * the search we should trigger,
   * this corresponds to `name` attribute of corresponding search-bar
   */

  override render() {
    return html`
      <button
        @click=${this.dispatchClickEvent}
        @keyup=${this._onKeyUp}
        part="button"
        role="button"
        class="search-button"
      >
        <slot> Search </slot>
      </button>
    `;
  }

  /**
   * Launch search by emitting the click event.
   */
  dispatchClickEvent() {
    this.dispatchEvent(new CustomEvent(BasicEvents.CLICK));
  }

  private _onKeyUp(event: Event) {
    const kbd_event = event as KeyboardEvent;
    if (kbd_event.key === 'Enter') {
      this.dispatchClickEvent();
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-button': SearchaliciousButton;
  }
}
