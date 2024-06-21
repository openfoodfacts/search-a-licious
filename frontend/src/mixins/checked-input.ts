import {Constructor} from './utils';
import {LitElement, PropertyValues} from 'lit';
import {property} from 'lit/decorators.js';
import {BasicEvents} from '../utils/enums';

export interface CheckedInputMixinInterface {
  checked: boolean;
  name: string;
  getInputElement(): HTMLInputElement | null;
  _dispatchChangeEvent(checked: boolean, name: string): void;
  refreshInput(): void;
  _handleChange(e: {target: HTMLInputElement}): void;
}

export const CheckedInputMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  class CheckedInputMixinClass extends superClass {
    /**
     * Represents the checked state of the input.
     * @type {boolean}
     */
    @property({type: Boolean})
    checked = false;

    /**
     * Represents the name of the input.
     * @type {string}
     */
    @property({type: String})
    name = '';

    getInputElement() {
      return this.shadowRoot?.querySelector('input');
    }

    _dispatchChangeEvent(checked: boolean, name: string) {
      const inputEvent = new CustomEvent(BasicEvents.CHANGE, {
        detail: {checked, name},
        bubbles: true,
        composed: true,
      });
      this.dispatchEvent(inputEvent);
    }
    refreshInput() {
      const inputElement = this.getInputElement();
      if (inputElement) {
        inputElement.checked = this.checked;
      }

      /**
       * Called when the element’s DOM has been updated and rendered.
       * @param {PropertyValues} _changedProperties - The changed properties.
       */
    }
    protected override updated(_changedProperties: PropertyValues) {
      this.refreshInput();
      super.updated(_changedProperties);
    }

    /**
     * Handles the change event on the radio.
     * @param {Event} e - The change event.
     */
    _handleChange(e: {target: HTMLInputElement}) {
      this.checked = e.target.checked;
      this._dispatchChangeEvent(this.checked, this.name);
    }
  }
  return CheckedInputMixinClass as Constructor<CheckedInputMixinInterface> & T;
};
