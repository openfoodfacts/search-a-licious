import {LitElement} from 'lit';
import {Constructor} from './utils';

/**
 * Interface for the DebounceMixin.
 * It defines the structure that DebounceMixin should adhere to.
 */
export interface DebounceMixinInterface {
  timeout?: number;
  debounce<F extends () => void>(func: F, wait?: number): void;
}

/**
 * A mixin class for debouncing function calls.
 * It extends the LitElement class and adds debouncing functionality.
 * It is used to prevent a function from being called multiple times in a short period of time.
 * It is usefull to avoid multiple calls to a function when the user is typing in an input field.
 * @param {Constructor<LitElement>} superClass - The superclass to extend from.
 * @returns {Constructor<DebounceMixinInterface> & T} - The extended class with debouncing functionality.
 */
export const DebounceMixin = <T extends Constructor<LitElement>>(
  superClass: T
): Constructor<DebounceMixinInterface> & T =>
  class extends superClass {
    timeout?: number = undefined;

    /**
     * Debounces a function call.
     * It delays the execution of the function until after wait milliseconds have elapsed since the last time this function was invoked.
     * @param {Function} func - The function to debounce.
     * @param {number} wait - The number of milliseconds to delay.
     */
    debounce<F extends () => void>(func: F, wait = 300): void {
      // eslint-disable-next-line @typescript-eslint/no-this-alias
      const self = this;
      clearTimeout(this.timeout);
      this.timeout = setTimeout(() => {
        this.timeout = undefined;
        func.bind(self)();
      }, wait);
    }
  } as Constructor<DebounceMixinInterface> & T;
