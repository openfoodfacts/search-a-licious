import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';
import {classMap} from 'lit/directives/class-map.js';
import {AutocompleteMixin, AutocompleteResult} from './mixins/autocomplete';
import {SearchaliciousEvents} from './utils/enums';

/**
 * Search autocomplete that can be used in facets to add terms that are not yet displayed (because they haven't enough elements).
 * It supports adding terms from suggested options but also terms that are not suggested.
 * Options are provided by the parent facet component that listen to `autocomplete-input` events to get input and fetch options accordingly
 * As a value is selected, an `autocomplete-submit` event is emitted so that parent facet can add the new value.
 * @extends {LitElement}
 * @slot - This slot is for the button contents, default to "Search" string.
 */
@customElement('searchalicious-autocomplete')
export class SearchaliciousAutocomplete extends AutocompleteMixin(LitElement) {
  static override styles = css`
    .search-autocomplete {
      position: relative;
      display: inline-block;
    }
    .search-autocomplete input {
      width: 100%;
      box-sizing: border-box;
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

  /**
   * Renders the possiblibility as list for user to select from
   * @returns {import('lit').TemplateResult<1>} The HTML template for the possible terms.
   */
  _renderPossibility() {
    return this.options.length
      ? this.options.map(
          (option, index) => html` <li
            class=${classMap({selected: index + 1 === this.currentIndex})}
            @click=${this.onClick(index)}
          >
            ${option.label}
          </li>`
        )
      : html`<li>No results found</li>`;
  }

  /**
   * This method is used to handle the input value.
   * @param value
   */
  override handleInput(value: string) {
    // we don't need a very specific event name
    // because it will be captured by the parent Facet element
    const inputEvent = new CustomEvent(
      SearchaliciousEvents.AUTOCOMPLETE_INPUT,
      {
        detail: {value: value},
        bubbles: true,
        composed: true,
      }
    );
    this.dispatchEvent(inputEvent);
  }

  /**
   * This method is used to submit the input value.
   * It is used to submit the input value after selecting an option.
   * @param {boolean} isSuggestion - A boolean value to check if the value is a suggestion or a free input from the user.
   */
  override submit(isSuggestion = false) {
    if (!this.value) return;

    const inputEvent = new CustomEvent(
      SearchaliciousEvents.AUTOCOMPLETE_SUBMIT,
      {
        // we send both value and label
        detail: {
          value: this.value,
          label: isSuggestion ? this.currentOption!.label : undefined,
        } as AutocompleteResult,
        bubbles: true,
        composed: true,
      }
    );
    this.dispatchEvent(inputEvent);
    this.resetInput();
  }

  /**
   * Renders the search autocomplete: input box and eventual list of possible choices.
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
          @input=${this.onInput}
          @keydown=${this.onKeyDown}
          autocomplete="off"
          @focus=${this.onFocus}
          @blur=${this.onBlur}
        />
        <ul class=${classMap({visible: this.visible && this.value.length})}>
          ${this.isLoading
            ? html`<li>Loading...</li>`
            : this._renderPossibility()}
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
