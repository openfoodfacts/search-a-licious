import {LitElement} from 'lit';
import {Constructor} from './utils';
import {property, state} from 'lit/decorators.js';
import {DebounceMixin, DebounceMixinInterface} from './debounce';
import {SuggestionSelectionOption} from '../interfaces/suggestion-interfaces';

/**
 * Interface for the Suggestion Selection mixin.
 */
export interface SuggestionSelectionMixinInterface
  extends DebounceMixinInterface {
  inputName: string;
  options: SuggestionSelectionOption[];
  selectedOption: SuggestionSelectionOption | undefined;
  inputValue: string;
  visible: boolean;
  isLoading: boolean;
  currentIndex: number;

  onInput(event: InputEvent): void;
  handleInput(value: string): void;
  blurInput(): void;
  resetInput(selectedOption?: SuggestionSelectionOption): void;
  submitSuggestion(isSuggestion?: boolean): void;
  handleArrowKey(direction: 'up' | 'down'): void;
  handleEnter(event: KeyboardEvent): void;
  handleEscape(): void;
  onKeyDown(event: KeyboardEvent): void;
  onClick(option: SuggestionSelectionOption): () => void;
  onFocus(): void;
  onBlur(): void;
}

/**
 * Type for suggestion result.
 */
export type SuggestionSelectionResult = {
  value: string;
  label?: string;
  id: string;
};

/**
 * This mixin handles the logic of having a list of suggestion,
 * and letting the user choose on suggestion.
 *
 * It factors the interaction logic but does not deal with the rendering.
 */
export const SuggestionSelectionMixin = <T extends Constructor<LitElement>>(
  superClass: T
): Constructor<SuggestionSelectionMixinInterface> & T => {
  class SuggestionSelectionMixinClass extends DebounceMixin(superClass) {
    @property({attribute: 'input-name'})
    inputName = 'suggestion';

    /**
     * The options for the suggestion.
     * It is provided by the parent component.
     */
    @property({attribute: false, type: Array})
    options: SuggestionSelectionOption[] = [];

    /**
     * index of suggestion about to be selected
     *
     * It mainly tracks current focused suggestion
     * when navigating with arrow keys
     */
    @state()
    currentIndex = 0;

    // track current input value
    @state()
    inputValue = '';

    /**
     * The option that was selected
     *
     * Note that it might be from outside the options list (for specific inputs)
     */
    selectedOption: SuggestionSelectionOption | undefined;

    @property({attribute: false})
    visible = false;

    @property({attribute: false})
    isLoading = false;

    getInput() {
      return this.shadowRoot!.querySelector('input');
    }

    /**
     * Handles the input event on the suggestion, that is when the option is suggested
     * and dispatch to handleInput
     * @param {InputEvent} event - The input event.
     */
    onInput(event: InputEvent) {
      const value = (event.target as HTMLInputElement).value;
      this.inputValue = value;
      this.handleInput(value);
    }

    /**
     * React on changing input
     *
     * This method is to be implemented by the component to ask for new suggestions based on the input value.
     * @param value the current input value
     */
    handleInput(value: string) {
      throw new Error(
        `handleInput method must be implemented for ${this} with ${value}`
      );
    }

    /**
     * This method is used to remove focus from the input element.
     * It is used to quit after selecting an option.
     */
    blurInput() {
      const input = this.getInput();
      if (input) {
        input.blur();
      }
    }

    /**
     * This method is used to reset the input value and blur it.
     * It is used to reset the input after a search.
     */
    resetInput(selectedOption?: SuggestionSelectionOption) {
      this.currentIndex = 0;
      const input = this.getInput();
      if (!input) {
        return;
      }
      // remove part of the text that generates the selection
      if (selectedOption) {
        input.value = input.value.replace(selectedOption?.input || '', '');
      } else {
        input.value = '';
      }
      this.blurInput();
    }

    /**
     * This method is used to submit the input value.
     * It is used to submit the input value after selecting an option.
     * @param {boolean} isSuggestion - A boolean value to check if the value is a suggestion.
     */
    submitSuggestion(isSuggestion = false) {
      throw new Error(
        `submit method must be implemented for ${this} with ${isSuggestion}`
      );
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
      let isSuggestion = false;
      if (this.currentIndex) {
        isSuggestion = true;
        this.selectedOption = this.options[this.currentIndex - 1];
      } else {
        // direct suggestion
        const value = (event.target as HTMLInputElement).value;
        this.selectedOption = {
          value: value,
          label: value,
          id: '--direct-suggestion--' + value,
          input: value,
        };
      }
      this.submitSuggestion(isSuggestion);
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
     * On a click on the suggestion option, we select it as value and submit it.
     * @param option - chosen option
     */
    onClick(option: SuggestionSelectionOption) {
      return () => {
        this.selectedOption = option;
        this.currentIndex = 0;
        this.submitSuggestion(true);
      };
    }

    /**
     * This method is used to handle the focus event on the input element.
     * It is used to show the suggestion options when the input is focused.
     */
    onFocus() {
      this.visible = true;
    }

    /**
     * This method is used to handle the blur event on the input element.
     * It is used to hide the suggestion options when the input is blurred.
     * It is debounced to avoid to quit before select with click.
     */
    onBlur() {
      this.debounce(() => {
        this.visible = false;
      });
    }
  }

  return SuggestionSelectionMixinClass as Constructor<SuggestionSelectionMixinInterface> &
    T;
};
