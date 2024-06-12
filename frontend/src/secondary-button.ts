import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {BasicEvents} from './utils/enums';

/**
 * A custom element that represents a secondary button for a search.
 * It sends a custom event "click" when clicked.
 * You can modify this variable to customize the button style :
 * - --secondary-button-padding
 *
 * @extends {LitElement}
 * @slot - This slot is for the button contents, default to "Reset" string.
 */
@customElement('searchalicious-secondary-button')
export class SearchaliciousSecondaryButton extends LitElement {
  /**
   * Styles for the secondary button.
   */
  static override styles = css`
    .secondary-button {
      background-color: black;
      border-radius: 3rem;
      border: none;
      color: white;
      padding: var(--secondary-button-padding, 0.5rem 2rem);
      text-align: center;
      text-decoration: none;
      display: inline-block;
      font-size: 1rem;
      margin-top: 0.5rem;
      cursor: pointer;
    }
  `;

  /**
   * Render function for the secondary button.
   * @returns {import('lit').TemplateResult<1>} The HTML template for the secondary button.
   */
  override render() {
    return html`
      <button
        @click=${this._onClick}
        @keyup=${this._onKeyUp}
        part="secondary-button"
        role="button"
        class="secondary-button"
      >
        <slot></slot>
      </button>
    `;
  }

  /**
   * Dispatches a secondary event.
   * @private
   */
  private _dispatchEvent() {
    this.dispatchEvent(
      new CustomEvent(BasicEvents.CLICK, {bubbles: true, composed: true})
    );
  }

  /**
   * Handles the click event on the secondary button.
   * @private
   */
  private _onClick() {
    this._dispatchEvent();
  }

  /**
   * Handles the keyup event on the secondary button to dispatch secondary event.
   * @param {Event} event - The keyup event.
   * @private
   */
  private _onKeyUp(event: Event) {
    const kbd_event = event as KeyboardEvent;
    if (kbd_event.key === 'Enter') {
      this._dispatchEvent();
    }
  }
}

declare global {
  /**
   * The HTMLElementTagNameMap interface represents a map of custom element tag names to custom element constructors.
   * Here, it's extended to include 'searchalicious-secondary-button' as a valid custom element tag name.
   */
  interface HTMLElementTagNameMap {
    'searchalicious-secondary-button': SearchaliciousSecondaryButton;
  }
}
