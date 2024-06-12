import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';

import {BasicEvents} from './utils/enums';

/**
 * A custom element that represents a button without background for a search.
 * It sends a custom event "click" when clicked.
 * It exists to have already styled button for secondary actions.
 * You can modify this variable to customize the button style :
 * --button-without-background-background-padding
 * --secondary-hover-color
 * @extends {LitElement}
 * @slot - This slot is for the button contents, default to "Search" string.
 */
@customElement('searchalicious-button-without-background')
export class SearchaliciousButtonWithoutBackground extends LitElement {
  static override styles = css`
    .button-without-background {
      background-color: transparent;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: none;
      border-radius: 3.5rem;
      cursor: pointer;
      padding: var(
        --button-without-background-background-padding,
        0.25rem 0.5rem
      );
    }
    .button-without-background:hover {
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
        part="button-without-background"
        role="button"
        class="button-without-background"
        type="button"
      >
        <slot></slot>
      </button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-button-without-background': SearchaliciousButtonWithoutBackground;
  }
}
