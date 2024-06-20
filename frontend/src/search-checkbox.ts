import {LitElement, html, PropertyValues, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {BasicEvents} from './utils/enums';

/**
 * A custom element that represents a checkbox.
 *
 * This component is useful to have state of variable reflected back in the checkbox,
 * overriding updated method.
 * @extends {LitElement}
 */
@customElement('searchalicious-checkbox')
export class SearchaliciousCheckbox extends LitElement {
  /**
   * The styles for the checkbox.
   * "appearance: none" is used to remove the default checkbox style.
   * We use an svg icon for the checked state, it is located in the public/icons folder.
   * @type {import('lit').CSSResult}
   */
  static override styles = css`
    .checkbox-wrapper {
      display: flex;
      align-items: center;
    }

    input[type='checkbox'] {
      cursor: pointer;
      position: relative;
      width: 20px;
      height: 20px;
      margin-right: 0;
      appearance: none;
      border: 1px solid black;
      background-color: transparent;
    }
    input[type='checkbox']:checked {
      background-color: black;
    }
    input[type='checkbox']:focus {
      outline: 1px solid blue;
    }
    input[type='checkbox']:checked:after {
      position: absolute;
      content: '';
      height: 12px;
      width: 12px;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: url('/static/icons/checkbox-check.svg') no-repeat center
        center;
    }

    label {
      cursor: pointer;
      padding-left: 8px;
    }
  `;
  /**
   * Represents the checked state of the checkbox.
   * @type {boolean}
   */
  @property({type: Boolean})
  checked = false;

  /**
   * Represents the name of the checkbox.
   * @type {string}
   */
  @property({type: String})
  name = '';

  /**
   * Refreshes the checkbox to reflect the current state of the `checked` property.
   */
  refreshCheckbox() {
    const inputElement = this.shadowRoot?.querySelector('input');
    if (inputElement) {
      inputElement.checked = this.checked;
    }
  }

  /**
   * Called when the element’s DOM has been updated and rendered.
   * @param {PropertyValues} _changedProperties - The changed properties.
   */
  protected override updated(_changedProperties: PropertyValues) {
    this.refreshCheckbox();
    super.updated(_changedProperties);
  }

  /**
   * Renders the checkbox.
   * @returns {import('lit').TemplateResult<1>} - The HTML template for the checkbox.
   */
  override render() {
    return html`
      <div class="checkbox-wrapper">
        <input
          part="checkbox"
          .name=${this.name}
          .id="${this.name}"
          type="checkbox"
          ?checked=${this.checked}
          @change=${this._handleChange}
        />
        <label for="${this.name}"><slot name="label">${this.name}</slot></label>
      </div>
    `;
  }

  /**
   * Handles the change event on the checkbox.
   * @param {Event} e - The change event.
   */
  _handleChange(e: {target: HTMLInputElement}) {
    this.checked = e.target.checked;
    const inputEvent = new CustomEvent(BasicEvents.CHANGE, {
      detail: {checked: this.checked, name: this.name},
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(inputEvent);
  }
}

declare global {
  /**
   * The HTMLElementTagNameMap interface represents a map of custom element tag names to custom element constructors.
   * Here, it's extended to include 'searchalicious-checkbox' as a valid custom element tag name.
   */
  interface HTMLElementTagNameMap {
    'searchalicious-checkbox': SearchaliciousCheckbox;
  }
}
