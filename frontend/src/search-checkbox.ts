import {LitElement, html, PropertyValues} from 'lit';
import {customElement, property} from 'lit/decorators.js';

@customElement('searchalicious-checkbox')
export class SearchaliciousCheckbox extends LitElement {
  @property({type: Boolean})
  checked = false;

  @property({type: String})
  name = '';

  refreshCheckbox() {
    const inputElement = this.shadowRoot?.querySelector('input');
    if (inputElement) {
      inputElement.checked = this.checked;
    }
  }
  protected override updated(_changedProperties: PropertyValues) {
    this.refreshCheckbox();
    super.updated(_changedProperties);
  }

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
  interface HTMLElementTagNameMap {
    'searchalicious-checkbox': SearchaliciousCheckbox;
  }
}
