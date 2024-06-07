import {LitElement} from 'lit';
import {Constructor} from './utils';
import {SearchaliciousCheckbox} from '../search-checkbox';
import {queryAssignedNodes} from 'lit/decorators';
export interface CheckboxMixinInterface {
  _checkboxNodes(): SearchaliciousCheckbox[];
  refreshCheckboxes(): void;
}
export const CheckboxMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  class CheckboxMixinClass extends superClass {
    @queryAssignedNodes({flatten: true})
    slotNodes!: Array<Node>;
    _checkboxNodes() {
      return (this.slotNodes as Array<Node>).filter(
        (node) => node instanceof SearchaliciousCheckbox
      ) as SearchaliciousCheckbox[];
    }

    refreshCheckboxes() {
      this._checkboxNodes().forEach((node) => {
        node.refreshCheckbox();
      });
    }
  }

  return CheckboxMixinClass as Constructor<CheckboxMixinInterface> & T;
};
