import {LitElement} from 'lit';
import {Constructor} from './utils';

export interface DebounceMixinInterface {
  timeout?: number;
  debounce<F extends () => void>(func: F, wait: number): () => void;
}

export const DebounceMixin = <T extends Constructor<LitElement>>(
  superClass: T
) =>
  class extends superClass {
    timeout?: number = undefined;

    debounce<F extends () => void>(func: F, wait: number = 300): () => void {
      return () => {
        clearTimeout(this.timeout);
        this.timeout = setTimeout(() => {
          this.timeout = undefined;
          func();
        }, wait);
      };
    }
  } as Constructor<T & DebounceMixinInterface>;
