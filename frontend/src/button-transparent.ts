import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';

import {BasicEvents} from './utils/enums';

/**
 * A custom element that represents a button without background for a search.
 * It sends a custom event "click" when clicked.
 * It exists to have already styled button for secondary actions.
 * You can modify this variable to customize the button style :
 * --button-transparent-padding
 * --secondary-hover-color
 * @extends {LitElement}
 * @slot - This slot is for the button contents, default to "Search" string.
 */
@customElement('searchalicious-button-transparent')
export class SearchaliciousButtonTransparent extends LitElement {
  static override styles = css`
    .button-transparent {
      background-color: transparent;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: none;
      border-radius: 3.5rem;
      cursor: pointer;
      padding: var(--button-transparent-padding, 0.25rem 0.5rem);
    }
    .button-transparent:hover {
      background-color: var(--secondary-hover-color, #cfac9e);
    }
  `;

  private _onClick() {
    this._dispatchEvent();
  }

  private _onKeyUp(event: Event) {
    const kbd_event = event as KeyboardEvent;
    if (kbd_event.key === 'Enter') {
      this._dispatchEvent();
    }
  }

  private _dispatchEvent() {
    this.dispatchEvent(
      new CustomEvent(BasicEvents.CLICK, {bubbles: true, composed: true})
    );
  }

  override render() {
    return html`
      <button
        @click=${this._onClick}
        @keyup=${this._onKeyUp}
        part="button-transparent"
        role="button"
        class="button-transparent"
        type="button"
      >
        <slot></slot>
      </button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-button-transparent': SearchaliciousButtonTransparent;
  }
}
