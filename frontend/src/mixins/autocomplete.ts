import {LitElement} from 'lit';
import {Constructor} from './utils';
import {property} from 'lit/decorators.js';
import {DebounceMixin, DebounceMixinInterface} from './debounce';

/**
 * Interface for the Autocomplete mixin.
 */
export interface AutocompleteMixinInterface extends DebounceMixinInterface {
  inputName: string;
  options: AutocompleteOption[];
  value: string;
  currentIndex: number;
  getOptionIndex: number;
  visible: boolean;
  isLoading: boolean;
  currentOption: AutocompleteOption | undefined;

  onInput(event: InputEvent): void;
  handleInput(value: string): void;
  blurInput(): void;
  resetInput(): void;
  submit(isSuggestion?: boolean): void;
  getAutocompleteValueByIndex(index: number): string;
  handleArrowKey(direction: 'up' | 'down'): void;
  handleEnter(event: KeyboardEvent): void;
  handleEscape(): void;
  onKeyDown(event: KeyboardEvent): void;
  onClick(index: number): () => void;
  onFocus(): void;
  onBlur(): void;
}
/**
 * Type for autocomplete option.
 */
export type AutocompleteOption = {
  value: string;
  label: string;
};
/**
 * Type for autocomplete result.
 */
export type AutocompleteResult = {
  value: string;
  label?: string;
};

/**
 * This mixin handles the logic of having a list of suggestion, 
 * and letting the user choose on suggestion.
 * 
 * It factors the interaction logic but does not deal with the rendering.
 */
export const AutocompleteMixin = <T extends Constructor<LitElement>>(
  superClass: T
): Constructor<AutocompleteMixinInterface> & T => {
  class AutocompleteMixinClass extends DebounceMixin(superClass) {
    @property({attribute: 'input-name'})
    inputName = 'autocomplete';

    /**
     * The options for the autocomplete.
     * It is provided by the parent component.
     */
    @property({attribute: false, type: Array})
    options: AutocompleteOption[] = [];

    // selected values
    @property()
    value = '';

    @property({attribute: false})
    currentIndex = 0;

    @property({attribute: false})
    visible = false;

    @property({attribute: false})
    isLoading = false;

    /**
     * This method is used to get the current index.
     * It remove the offset of 1 because the currentIndex is 1-based.
     * @returns {number} The current index.
     */
    get getOptionIndex() {
      return this.currentIndex - 1;
    }

    get currentOption() {
      return this.options[this.getOptionIndex];
    }

    /**
     * Handles the input event on the autocomplete and dispatch custom event : "autocomplete-input".
     * @param {InputEvent} event - The input event.
     */
    onInput(event: InputEvent) {
      const value = (event.target as HTMLInputElement).value;
      this.value = value;
      this.handleInput(value);
    }

    handleInput(value: string) {
      throw new Error(`handleInput method must be implemented for ${this} with ${value}`);
    }
    /**
     * This method is used to remove focus from the input element.
     * It is used to quit after selecting an option.
     */
    blurInput() {
      const input = this.shadowRoot!.querySelector('input');
      if (input) {
        input.blur();
      }
    }

    /**
     * This method is used to reset the input value and blur it.
     * It is used to reset the input after a search.
     */
    resetInput() {
      this.value = '';
      this.currentIndex = 0;
      this.blurInput();
    }

    /**
     * This method is used to submit the input value.
     * It is used to submit the input value after selecting an option.
     * @param {boolean} isSuggestion - A boolean value to check if the value is a suggestion.
     */
    submit(isSuggestion = false) {
      throw new Error(`submit method must be implemented for ${this} with ${isSuggestion}`);
    }

    /**
     * Handles keyboard event to navigate the suggestion list
     * @param {string} direction - The direction of the arrow key event.
     */
    handleArrowKey(direction: 'up' | 'down') {
      const offset = direction === 'down' ? 1 : -1;
      const maxIndex = this.options.length + 1;
      this.currentIndex = (this.currentIndex + offset + maxIndex) % maxIndex;
    }

    /**
     * When Enter is pressed:
     *   * if an option was selected (using keyboard arrows) it becomes the value
     *   * otherwise the input string is the value
     * We then submit the value.
     * @param event
     */
    handleEnter(event: KeyboardEvent) {
      let isAutoComplete = false;
      if (this.currentIndex) {
        isAutoComplete = true;
        this.value = this.currentOption!.value;
      } else {
        const value = (event.target as HTMLInputElement).value;
        this.value = value;
      }
      this.submit(isAutoComplete);
    }

    /**
     * This method is used to handle the escape key event.
     */
    handleEscape() {
      this.blurInput();
    }

    /**
     * dispatch key events according to the key pressed (arrows or enter)
     * @param event
     */
    onKeyDown(event: KeyboardEvent) {
      switch (event.key) {
        case 'ArrowDown':
          this.handleArrowKey('down');
          return;
        case 'ArrowUp':
          this.handleArrowKey('up');
          return;
        case 'Enter':
          this.handleEnter(event);
          return;
        case 'Escape':
          this.handleEscape();
          return;
      }
    }

    /**
     * On a click on the autocomplete option, we select it as value and submit it.
     * @param index
     */
    onClick(index: number) {
      return () => {
        this.value = this.options[index].value;
        // we need to increment the index because currentIndex is 1-based
        this.currentIndex = index + 1;
        this.submit(true);
      };
    }

    /**
     * This method is used to handle the focus event on the input element.
     * It is used to show the autocomplete options when the input is focused.
     */
    onFocus() {
      this.visible = true;
    }

    /**
     * This method is used to handle the blur event on the input element.
     * It is used to hide the autocomplete options when the input is blurred.
     * It is debounced to avoid to quit before select with click.
     */
    onBlur() {
      this.debounce(() => {
        this.visible = false;
      });
    }
  }

  return AutocompleteMixinClass as Constructor<AutocompleteMixinInterface> & T;
};
