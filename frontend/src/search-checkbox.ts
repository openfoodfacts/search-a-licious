import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {CheckedInputMixin} from './mixins/checked-input';

/**
 * A custom element that represents a checkbox.
 *
 * This component is useful to have state of variable reflected back in the checkbox,
 * overriding updated method.
 * @extends {LitElement}
 */
@customElement('searchalicious-checkbox')
export class SearchaliciousCheckbox extends CheckedInputMixin(LitElement) {
  /**
   * The styles for the checkbox.
   * "appearance: none" is used to remove the default checkbox style.
   * margin-right: 0 is used to remove the default margin between the checkbox and the label.
   * We use an svg icon for the checked state, it is located in the public/icons folder.
   * @type {import('lit').CSSResult}
   */
  static override styles = css`
    .checkbox-wrapper {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
    }

    input[type='checkbox'] {
      cursor: pointer;
      position: relative;
      width: 20px;
      height: 20px;
      margin-right: 0;
      appearance: none;
      border: 1px solid var(--searchalicious-checkbox-color, black);
      background-color: transparent;
    }
    input[type='checkbox']:checked {
      background-color: var(--searchalicious-checkbox-color, black);
    }
    input[type='checkbox']:focus {
      outline: 1px solid var(--searchalicious-checkbox-focus-color, black);
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
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-checkbox': SearchaliciousCheckbox;
  }
}
