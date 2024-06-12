import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';

/**
 * A custom element that represents a reset button for a search.
 * It sends a custom event "reset" when clicked.
 * @extends {LitElement}
 * @slot - This slot is for the button contents, default to "Reset" string.
 */
@customElement('searchalicious-reset-button')
export class SearchaliciousResetButton extends LitElement {
  /**
   * Styles for the reset button.
   */
  static override styles = css`
    .reset-button {
      background-color: black;
      border-radius: 3rem;
      border: none;
      color: white;
      padding: 0.5rem 1rem;
      text-align: center;
      text-decoration: none;
      display: inline-block;
      font-size: 1rem;
      margin-top: 0.5rem;
      cursor: pointer;
      width: 100%;
    }
  `;

  /**
   * Render function for the reset button.
   * @returns {import('lit').TemplateResult<1>} The HTML template for the reset button.
   */
  override render() {
    return html`
      <button
        @click=${this._onClick}
        @keyup=${this._onKeyUp}
        part="reset-button"
        role="button"
        class="reset-button"
      >
        <slot> Reset </slot>
      </button>
    `;
  }

  /**
   * Dispatches a reset event.
   * @private
   */
  private _dispatchResetEvent() {
    this.dispatchEvent(
      new CustomEvent('reset', {bubbles: true, composed: true})
    );
  }

  /**
   * Handles the click event on the reset button.
   * @private
   */
  private _onClick() {
    this._dispatchResetEvent();
  }

  /**
   * Handles the keyup event on the reset button to dispatch reset event.
   * @param {Event} event - The keyup event.
   * @private
   */
  private _onKeyUp(event: Event) {
    const kbd_event = event as KeyboardEvent;
    if (kbd_event.key === 'Enter') {
      this._dispatchResetEvent();
    }
  }
}

declare global {
  /**
   * The HTMLElementTagNameMap interface represents a map of custom element tag names to custom element constructors.
   * Here, it's extended to include 'searchalicious-reset-button' as a valid custom element tag name.
   */
  interface HTMLElementTagNameMap {
    'searchalicious-reset-button': SearchaliciousResetButton;
  }
}
