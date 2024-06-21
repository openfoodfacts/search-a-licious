import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {CheckedInputMixin} from './mixins/checked-input';

/**
 * A custom element that represents a toggle.
 *
 * This component is useful to have state of variable reflected back in the toggle,
 * overriding updated method.
 * @extends {LitElement}
 */
@customElement('searchalicious-toggle')
export class SearchaliciousToggle extends CheckedInputMixin(LitElement) {
  /**
   * The styles for the toggle.
   * @type {import('lit').CSSResult}
   */
  static override styles = css`
    .toggle-wrapper {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
    }

    label {
      cursor: pointer;
      padding-right: 8px;
    }

    .toggle {
      cursor: pointer;
      position: relative;
      display: inline-block;
      width: 30px;
      height: 17px;
      flex-shrink: 0;
    }

    .toggle input {
      display: none;
    }

    .slider {
      position: absolute;
      cursor: pointer;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background-color: var(
        --searchalicious-toggle-inactive-background-color,
        grey
      );
      transition: 0.4s;
      border-radius: 17px;
    }

    .slider:before {
      position: absolute;
      content: '';
      height: 13px;
      width: 13px;
      left: 2px;
      bottom: 2px;
      background-color: var(--searchalicious-toggle-circle-color, white);
      transition: 0.4s;
      border-radius: 50%;
    }
    input[type='checkbox']:checked + .slider {
      background-color: var(
        --searchalicious-toggle-active-background-color,
        black
      );
    }
    input[type='checkbox']:checked + .slider:before {
      transform: translateX(13px);
    }
  `;

  onClick() {
    const inputElement = this.getInputElement();
    if (!inputElement) {
      return;
    }
    inputElement.checked = !inputElement.checked;
    this.checked = !this.checked;
    this._dispatchChangeEvent(this.checked, this.name);
  }

  /**
   * Renders the toggle.
   * @returns {import('lit').TemplateResult<1>} - The HTML template for the toggle.
   */
  override render() {
    return html`
      <div class="toggle-wrapper">
        <label for="${this.name}"><slot name="label">${this.name}</slot></label>
        <div class="toggle">
          <input
            part="toggle-input"
            .name=${this.name}
            .id="${this.name}"
            type="checkbox"
            ?checked=${this.checked}
            @change=${this._handleChange}
          />
          <span class="slider" @click=${this.onClick}></span>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-toggle': SearchaliciousToggle;
  }
}
