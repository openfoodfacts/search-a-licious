import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {SearchaliciousSearchMixin} from './mixins/search-ctl';
import {SearchaliciousTermsMixin} from './mixins/suggestions-ctl';
import {AutocompleteMixin} from './mixins/autocomplete';
import {classMap} from 'lit/directives/class-map.js';
import {removeLangFromTermId} from './utils/taxonomies';

/**
 * The search bar element
 *
 * This is the main component, it will enable the input of the search query
 * and it also manage all the search thanks to SearchaliciousSearchMixin inheritance.
 */
@customElement('searchalicious-bar')
export class SearchaliciousBar extends AutocompleteMixin(
  SearchaliciousTermsMixin(SearchaliciousSearchMixin(LitElement))
) {
  static override styles = css`
    :host {
      display: block;
      padding: 5px;
    }

    .search-bar {
      position: relative;
    }

    /* Search suggestions list */
    .search-bar ul {
      --left-offset: 8px;
      position: absolute;
      left: var(--left-offset);
      background-color: LightYellow;
      border: 1px solid #ccc;
      width: 100%;
      width: calc(100% - var(--left-offset) - 1px);
      z-index: 1000;
      list-style: none;
      padding: 0;
      margin: 0;
    }

    ul li {
      cursor: pointer;
    }

    ul li:hover,
    ul li.selected {
      background-color: var(
        --searchalicious-autocomplete-selected-background-color,
        #cfac9e
      );
    }
  `;

  /**
   * Taxonomies we want to use for suggestions
   */
  @property({type: String, attribute: 'taxonomies'})
  taxonomies = '';

  /**
   * Place holder in search bar
   */
  @property()
  placeholder = 'Search...';

  /**
   * It parses the string taxonomies attribute and returns an array
   */
  get parsedTaxonomies() {
    return this.taxonomies.split(',');
  }

  /**
   * Handle the input event
   * It will update the query and call the getTaxonomiesTerms method to show suggestions
   * @param value
   */
  override handleInput(value: string) {
    this.query = value;
    this.debounce(() => {
      this.getTaxonomiesTerms(value, this.parsedTaxonomies).then(() => {
        this.options = this.terms.map((term) => ({
          value: term.text,
          label: term.text,
        }));
      });
    });
  }

  /**
   * Submit - might either be selecting  a suggestion or submitting a search expression
   */
  override submit(isSuggestion?: boolean) {
    console.log(this.query, this.value, isSuggestion);
    // If the value is a suggestion, select the term and reset the input otherwise search
    if (isSuggestion) {
      this.selectTermByTaxonomy(
        this.terms[this.getOptionIndex].taxonomy_name,
        removeLangFromTermId(this.terms[this.getOptionIndex].id)
      );
      this.resetInput();
      this.query = '';
    } else {
      this.query = this.value;
      this.blurInput();
    }
    this.search();
  }

  /**
   * Render the suggestions when the input is focused and the value is not empty
   */
  renderSuggestions() {
    // Don't show suggestions if the input is not focused or the value is empty or there are no suggestions
    if (!this.visible || !this.value || this.terms.length === 0) {
      return html``;
    }

    return html`
      <ul>
        ${this.terms.map(
          (term, index) => html`
            <li
              class=${classMap({selected: index + 1 === this.currentIndex})}
              @click=${this.onClick(index)}
            >
              <searchalicious-term-line
                .term=${term}
              ></searchalicious-term-line>
            </li>
          `
        )}
      </ul>
    `;
  }

  override render() {
    return html`
      <div class="search-bar" part="wrapper">
        <input
          type="text"
          name="q"
          @input=${this.onInput}
          @keydown=${this.onKeyDown}
          @focus="${this.onFocus}"
          @blur="${this.onBlur}"
          .value=${this.value}
          placeholder=${this.placeholder}
          part="input"
          autocomplete="off"
        />
        ${this.renderSuggestions()}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-bar': SearchaliciousBar;
  }
}
