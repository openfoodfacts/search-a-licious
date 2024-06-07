import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';

/**
 * An optional search reset button element that launch the search.
 *
 * @slot - goes in button contents, default to "Reset" string
 */
@customElement('searchalicious-reset-button')
export class SearchaliciousResetButton extends LitElement {
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
   * the search we should trigger,
   * this corresponds to `name` attribute of corresponding search-bar
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

  private _dispatchResetEvent() {
    this.dispatchEvent(
      new CustomEvent('reset', {bubbles: true, composed: true})
    );
  }
  /**
   * Launch search by emitting the LAUNCH_SEARCH signal
   */
  private _onClick() {
    this._dispatchResetEvent();
  }

  private _onKeyUp(event: Event) {
    const kbd_event = event as KeyboardEvent;
    if (kbd_event.key === 'Enter') {
      this._dispatchResetEvent();
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-reset-button': SearchaliciousResetButton;
  }
}
