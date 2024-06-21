import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {CheckedInputMixin} from './mixins/checked-input';

/**
 * A custom element that represents a radio.
 *
 * This component is useful to have state of variable reflected back in the radio,
 * overriding updated method.
 * @extends {LitElement}
 */
@customElement('searchalicious-radio')
export class SearchaliciousRadio extends CheckedInputMixin(LitElement) {
  /**
   * The styles for the radio.
   * @type {import('lit').CSSResult}
   */
  static override styles = css`
    .radio-wrapper {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
    }

    input[type='radio'] {
      cursor: pointer;
      position: relative;
      flex-shrink: 0;
      width: 20px;
      height: 20px;
      margin-right: 0;
      appearance: none;
      border: 1px solid var(--searchalicious-radio-color, black);
      background-color: transparent;
      border-radius: 50%;
    }

    input[type='radio']:checked {
    }

    input[type='radio']:focus {
      outline: 1px solid var(--searchalicious-radio-focus-color, black);
    }

    input[type='radio']:checked:after {
      position: absolute;
      content: '';
      height: 14px;
      width: 14px;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      border-radius: 50%;
      background-color: var(--searchalicious-radio-color, black);
    }

    label {
      cursor: pointer;
      padding-left: 8px;
    }
  `;

  /**
   * Allows or disallows the radio to be unchecked.
   */
  @property({type: Boolean, attribute: 'can-be-unchecked'})
  canBeUnchecked = false;

  /**
   * Represents the id of the input.
   */
  @property({type: String})
  inputId = '';

  /**
   * Allows for the radio to be unchecked.
   * @param {Event} e - The event object.
   */
  _handleClick() {
    if (this.canBeUnchecked && this.checked) {
      this.checked = false;
      this._dispatchChangeEvent(this.checked, this.name);
    }
  }
  /**
   * Renders the radio.
   * @returns {import('lit').TemplateResult<1>} - The HTML template for the radio.
   */
  override render() {
    return html`
      <div class="radio-wrapper">
        <input
          part="radio"
          .name=${this.name}
          .id="${this.inputId}"
          type="radio"
          ?checked=${this.checked}
          @change=${this._handleChange}
          @click="${this._handleClick}"
        />
        <label for="${this.inputId}">
          <slot name="label">${this.label}</slot>
        </label>
      </div>
    `;
  }
}
declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-radio': SearchaliciousRadio;
  }
}
