import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {DebounceMixin} from './mixins/debounce';
import {classMap} from 'lit/directives/class-map.js';
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
      background-color: #cfac9e;
    }

    ul.visible {
      display: block;
    }
  `;

  @property({attribute: 'input-name'})
  inputName = 'autocomplete';

  @property({attribute: false, type: Array})
  options: string[] = [];
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

  blurInput() {
    const input = this.shadowRoot!.querySelector('input');
    if (input) {
      input.blur();
    }
  }
  submit() {
    if (!this.value) return;

    const inputEvent = new CustomEvent('autocomplete-submit', {
      detail: {value: this.value},
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(inputEvent);
    this.value = '';
    this.currentIndex = 0;
    this.blurInput();
  }

  handleKeyDown(event: KeyboardEvent) {
    const maxIndex = this.options.length + 1;

    if (event.key === 'ArrowDown') {
      this.currentIndex = (this.currentIndex + 1) % maxIndex;
    } else if (event.key === 'ArrowUp') {
      this.currentIndex = (this.currentIndex - 1 + maxIndex) % maxIndex;
    }
    if (event.key === 'Enter') {
      if (this.currentIndex) {
        this.value = this.options[this.currentIndex];
      } else {
        const value = (event.target as HTMLInputElement).value;
        this.value = value;
      }
      this.submit();
    }
  }

  onClick(index: number) {
    return () => {
      this.value = this.options[index];
      this.submit();
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
            ${option}
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
