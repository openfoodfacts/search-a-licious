import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {DebounceMixin} from './mixins/debounce';
import {classMap} from 'lit/directives/class-map.js';
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
 * A custom element that represents a search autocomplete.
 * This component is designed to be reused in other components.
 * Options it is used to provide a list of possible terms to autocomplete.
 * Every time you type in the input, it will dispatch a custom event "autocomplete-input".
 * Every time you select an option: by enter or click, it will dispatch a custom event "autocomplete-submit".
 * @extends {LitElement}
 * @slot - This slot is for the button contents, default to "Search" string.
 */
@customElement('searchalicious-autocomplete')
export class SearchaliciousAutocomplete extends DebounceMixin(LitElement) {
  static override styles = css`
    .search-autocomplete {
      position: relative;
      display: inline-block;
    }

    ul {
      display: none;
      position: absolute;
      width: 100%;
      max-width: 100%;
      background-color: white;
      border: 1px solid black;
      list-style-type: none;
      padding: 0;
      margin: 0;
    }

    ul li {
      padding: 0.5em;
      cursor: pointer;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    ul li:hover,
    ul li.selected {
      background-color: var(
        --searchalicious-autocomplete-selected-background-color,
        #cfac9e
      );
    }

    ul.visible {
      display: block;
    }
  `;

  @property({attribute: 'input-name'})
  inputName = 'autocomplete';

  @property({attribute: false, type: Array})
  options: AutocompleteOption[] = [];
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
  getCurrentIndex() {
    return this.currentIndex - 1;
  }

  /**
   * Handles the input event on the autocomplete and dispatch custom event : "autocomplete-input".
   * @param {InputEvent} event - The input event.
   */
  handleInput(event: InputEvent) {
    const value = (event.target as HTMLInputElement).value;
    this.value = value;
    // we don't need a very specific event name
    // because it will be captured by the parent Facet element
    // we don't need a very specific event name
    // because it will be captured by the parent Facet element
    const inputEvent = new CustomEvent('autocomplete-input', {
      detail: {value: value},
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(inputEvent);
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
    if (!this.value) return;

    const inputEvent = new CustomEvent('autocomplete-submit', {
      // we send both value and label
      detail: {
        value: this.value,
        label: isSuggestion
          ? this.options[this.getCurrentIndex()].label
          : undefined,
      } as AutocompleteResult,
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(inputEvent);
    this.resetInput();
  }

  /**
   * This method is used to get the autocomplete value by index.
   * @param {number} index - The index of the autocomplete value.
   * @returns {string} The autocomplete value.
   */
  getAutocompleteValueByIndex(index: number) {
    return this.options[index].value;
  }

  /**
   * This method is used to handle the arrow key events.
   * @param {string} direction - The direction of the arrow key event.
   */
  handleArrowKey(direction: 'up' | 'down') {
    const offset = direction === 'down' ? 1 : -1;
    const maxIndex = this.options.length + 1;
    this.currentIndex = (this.currentIndex + offset + maxIndex) % maxIndex;
  }

  /**
   * This method is used to handle the enter key event.
   * @param event
   */
  handleEnter(event: KeyboardEvent) {
    let isAutoComplete = false;
    if (this.currentIndex) {
      isAutoComplete = true;
      this.value = this.getAutocompleteValueByIndex(this.getCurrentIndex());
    } else {
      const value = (event.target as HTMLInputElement).value;
      this.value = value;
    }
    this.submit(isAutoComplete);
  }

  /**
   * This method is used to handle the key down event.
   * It is used to handle the arrow key and enter key events.
   * @param event
   */
  handleKeyDown(event: KeyboardEvent) {
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
    }
  }

  /**
   * This method is used to handle the click event on the autocomplete option.
   * @param index
   */
  onClick(index: number) {
    return () => {
      this.value = this.getAutocompleteValueByIndex(index);
      // we need to increment the index because currentIndex is 1-based
      this.currentIndex = index + 1;
      this.submit(true);
    };
  }

  /**
   * This method is used to handle the focus event on the input element.
   * It is used to show the autocomplete options when the input is focused.
   */
  handleFocus() {
    this.visible = true;
  }

  /**
   * This method is used to handle the blur event on the input element.
   * It is used to hide the autocomplete options when the input is blurred.
   * It is debounced to avoid to quit before select with click.
   */
  handleBlur() {
    this.debounce(() => {
      this.visible = false;
    });
  }

  /**
   * This method is used to render the possible terms.
   * @returns {import('lit').TemplateResult<1>} The HTML template for the possible terms.
   */
  _renderPossibleTerms() {
    return this.options.length
      ? this.options.map(
          (option, index) => html` <li
            class=${index + 1 === this.currentIndex && 'selected'}
            @click=${this.onClick(index)}
          >
            ${option.label}
          </li>`
        )
      : html`<li>No results found</li>`;
  }

  /**
   * This method is used to render the search autocomplete.
   */
  override render() {
    return html`
      <span class="search-autocomplete" part="search-autocomplete">
        <input
          part="search-autocomplete-input"
          type="text"
          name="${this.inputName}"
          id="${this.inputName}"
          .value=${this.value}
          @input=${this.handleInput}
          @keydown=${this.handleKeyDown}
          autocomplete="off"
          @focus=${this.handleFocus}
          @blur=${this.handleBlur}
        />
        <ul class=${classMap({visible: this.visible && this.value.length})}>
          ${this.isLoading
            ? html`<li>Loading...</li>`
            : this._renderPossibleTerms()}
        </ul>
      </span>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-autocomplete': SearchaliciousAutocomplete;
  }
}
