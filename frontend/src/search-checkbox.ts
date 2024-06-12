import {LitElement, html, PropertyValues} from 'lit';
import {customElement, property} from 'lit/decorators.js';

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
      <input
        part="checkbox"
        .name=${this.name}
        .id="${this.name}"
        type="checkbox"
        ?checked=${this.checked}
        @change=${this._handleChange}
      />
    `;
  }

  /**
   * Handles the change event on the checkbox.
   * @param {Event} e - The change event.
   */
  _handleChange(e: {target: HTMLInputElement}) {
    this.checked = e.target.checked;
    const inputEvent = new CustomEvent('change', {
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
