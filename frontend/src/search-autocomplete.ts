import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {DebounceMixin} from './mixins/debounce';
import {classMap} from 'lit/directives/class-map.js';

export type AutocompleteOption = {
  value: string;
  label: string;
};
export type AutocompleteResult = {
  value: string;
  label?: string;
};

/**
 * An optional search autocomplete element that launch the search.
 *
 * @slot - goes in button contents, default to "Search" string
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

  handleInput(event: InputEvent) {
    const value = (event.target as HTMLInputElement).value;
    this.value = value;
    const inputEvent = new CustomEvent('autocomplete-input', {
      detail: {value: value},
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(inputEvent);
  }
  /**
   * This method is used to remove focus from the input element.
   * It first selects the input element from the shadow DOM,
   * then checks if the input element exists and if so, calls the blur method on it.
   * The blur method removes focus from the input element.
   */
  blurInput() {
    const input = this.shadowRoot!.querySelector('input');
    if (input) {
      input.blur();
    }
  }

  resetInput() {
    this.value = '';
    this.currentIndex = 0;
    this.blurInput();
  }
  submit(isSuggestion = false) {
    if (!this.value) return;

    const inputEvent = new CustomEvent('autocomplete-submit', {
      // we send both value and label
      detail: {
        value: this.value,
        label: isSuggestion ? this.options[this.currentIndex].label : undefined,
      } as AutocompleteResult,
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(inputEvent);
    this.resetInput();
  }

  getAutocompleteValueByIndex(index: number) {
    return this.options[index].value;
  }

  handleArrowDown() {
    this.currentIndex = (this.currentIndex + 1) % this.options.length;
  }
  handleArrowUp() {
    this.currentIndex =
      (this.currentIndex - 1 + this.options.length) % this.options.length;
  }
  handleEnter(event: KeyboardEvent) {
    let isAutoComplete = false;
    if (this.currentIndex) {
      isAutoComplete = true;
      this.value = this.getAutocompleteValueByIndex(this.currentIndex);
    } else {
      const value = (event.target as HTMLInputElement).value;
      this.value = value;
    }
    this.submit(isAutoComplete);
  }
  handleKeyDown(event: KeyboardEvent) {
    switch (event.key) {
      case 'ArrowDown':
        this.handleArrowDown();
        return;
      case 'ArrowUp':
        this.handleArrowUp();
        return;
      case 'Enter':
        this.handleEnter(event);
    }
  }

  onClick(index: number) {
    return () => {
      this.value = this.getAutocompleteValueByIndex(index);
      this.submit(true);
    };
  }

  handleFocus() {
    this.visible = true;
  }
  handleBlur() {
    this.debounce(() => {
      this.visible = false;
    });
  }

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
  override render() {
    return html`
      <span class="search-autocomplete" part="search-autocomplete">
        <input
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
