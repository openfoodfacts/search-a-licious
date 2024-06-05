import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {DebounceMixin} from './mixins/debounce';

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
      background-color: white;
      border: 1px solid black;
      list-style-type: none;
      padding: 0;
      margin: 0;
    }

    ul li:hover,
    ul li.selected {
      background-color: #cfac9e;
    }

    ul.visible {
      display: block;
    }
  `;

  @property({type: String, attribute: 'input-name'})
  inputName = 'autocomplete';

  @property({attribute: false, type: Array})
  options = [];
  @property({type: String})
  value: string = '';

  @property({attribute: false})
  currentIndex: number = 0;

  @property({attribute: false})
  visible: boolean = false;

  handleInput(event: InputEvent) {
    const inputEvent = new CustomEvent('autocomplete-input', {
      detail: {value: event.target!.value},
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
        this.value = event.target!.value;
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
  render() {
    return html`
      <span class="search-autocomplete" part="search-autocomplete">
        <input
          type="text"
          name="${this.inputName}"
          .value=${this.value}
          @input=${this.handleInput}
          @keydown=${this.handleKeyDown}
          autocomplete="off"
          @focus=${this.handleFocus}
          @blur=${this.handleBlur}
        />
        <ul class="${this.visible ? 'visible' : ''}">
          ${this.options.map(
            (option, index) => html` <li
              class=${index + 1 === this.currentIndex && 'selected'}
              @click=${this.onClick(index)}
            >
              ${option} ${index}
            </li>`
          )}
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
