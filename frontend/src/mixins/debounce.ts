import {LitElement} from 'lit';
import {Constructor} from './utils';

export interface DebounceMixinInterface {
  timeout?: number;
  debounce<F extends () => void>(func: F, wait?: number): void;
}

export const DebounceMixin = <T extends Constructor<LitElement>>(
  superClass: T
) =>
  class extends superClass {
    timeout?: number = undefined;

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
