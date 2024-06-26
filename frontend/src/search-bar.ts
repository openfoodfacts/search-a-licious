import {LitElement, html, css, nothing} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {SearchaliciousSearchMixin} from './mixins/search-ctl';
import {localized, msg} from '@lit/localize';
import {setLocale} from './localization/main';
import {SearchaliciousTermsMixin} from './mixins/suggestions-ctl';
import {SuggestionSelectionMixin} from './mixins/suggestion-selection';
import {classMap} from 'lit/directives/class-map.js';
import {removeLangFromTermId} from './utils/taxonomies';
import {searchBarInputAndButtonStyle} from './css/header';
import {SearchaliciousEvents} from './utils/enums';

/**
 * The search bar element
 *
 * This is the main component, it will enable the input of the search query
 * and it also manage all the search thanks to SearchaliciousSearchMixin inheritance.
 */
@customElement('searchalicious-bar')
@localized()
export class SearchaliciousBar extends SuggestionSelectionMixin(
  SearchaliciousTermsMixin(SearchaliciousSearchMixin(LitElement))
) {
  static override styles = [
    searchBarInputAndButtonStyle,
    css`
      :host {
        display: block;
        padding: 5px;
      }

      .search-bar {
        position: relative;
        display: flex;
        align-items: center;
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

      .button-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: var(--searchalicious-button-text-color, white);
      }

      .button-content span {
        margin-right: 0.5rem;
        margin-left: 0.3rem;
      }

      .input-wrapper {
        position: relative;
      }

      searchalicious-icon-cross {
        position: absolute;
        top: 0;
        right: 0;
        padding: 0.5rem;
        cursor: pointer;
      }

      searchalicious-button-transparent {
        margin-left: 0.5rem;
      }
    `,
  ];

  /**
   * Placeholder attribute is stored in a private variable to be able to use the msg() function
   * it stores the placeholder attribute value if it is set
   * @private
   */
  private _placeholder?: string;

  /**
   * Taxonomies we want to use for suggestions
   */
  @property({type: String, attribute: 'suggestions'})
  suggestions = '';

  /**
   * Place holder in search bar
   */
  @property()
  // it is mandatory to have a getter and setter for the property because of msg() function. doc : https://lit.dev/docs/localization/best-practices/#ensure-re-evaluation-on-render
  get placeholder() {
    return (
      this._placeholder ?? msg('Search...', {desc: 'Search bar placeholder'})
    );
  }
  set placeholder(value: string) {
    this._placeholder = value;
  }

  /**
   * Check if the search button text should be displayed
   */
  get showSearchButtonText() {
    return this.isQueryChanged || this.isFacetsChanged;
  }

  /**
   * Check if the filters can be reset
   * Filters is facets filters and query
   */
  get canReset() {
    const isQueryChanged = this.query || this.isQueryChanged;
    const facetsChanged = this._facetsFilters() || this.isFacetsChanged;
    return isQueryChanged || facetsChanged;
  }

  /**
   * It parses the string suggestions attribute and returns an array
   */
  get parsedSuggestions() {
    return this.suggestions.split(',');
  }

  constructor() {
    super();

    // allow to set the locale from the browser
    // @ts-ignore
    window.setLocale = setLocale;
  }

  /**
   * Handle the input event
   * It will update the query and call the getTaxonomiesTerms method to show suggestions
   * @param value
   */
  override handleInput(value: string) {
    this.value = value;
    this.query = value;
    this.debounce(() => {
      this.getTaxonomiesTerms(value, this.parsedSuggestions).then(() => {
        this.options = this.terms.map((term) => ({
          value: term.text,
          label: term.text,
        }));
      });
    });
  }

  /**
   * Submit - might either be selecting a suggestion or submitting a search expression
   */
  override submit(isSuggestion?: boolean) {
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
              <searchalicious-suggestion-entry
                .term=${term}
              ></searchalicious-suggestion-entry>
            </li>
          `
        )}
      </ul>
    `;
  }

  /**
   * Reset the input value, blur it and search with empty query.
   */
  onResetInput = () => {
    this.query = '';
    this.lastQuery = '';
    this.resetInput();
  };

  /**
   * Reset the facets filters, query and search with empty query.
   */
  onReset() {
    this.onResetInput();
    this.resetFacets(false);
    this.search();
  }

  onClickSearch() {
    this.search();
  }

  override connectedCallback() {
    super.connectedCallback();

    this.addEventHandler(SearchaliciousEvents.FACET_SELECTED, () => {
      this.requestUpdate();
    });
  }

  override disconnectedCallback() {
    super.disconnectedCallback();

    this.removeEventHandler(SearchaliciousEvents.FACET_SELECTED, () => {
      this.requestUpdate();
    });
  }
  override render() {
    return html`
      <div class="search-bar" part="wrapper">
        <div class="input-wrapper" part="input-wrapper">
          <input
            class="search-input"
            type="text"
            name="q"
            @input=${this.onInput}
            @keydown=${this.onKeyDown}
            @focus="${this.onFocus}"
            @blur="${this.onBlur}"
            .value=${this.query}
            placeholder=${this.placeholder}
            part="input"
            autocomplete="off"
          />
          ${this.renderSuggestions()}
        </div>
        <div>
          <searchalicious-button
            :search-name="${this.name}"
            @click=${this.onClickSearch}
          >
            <div class="button-content">
              <searchalicious-icon-search></searchalicious-icon-search>
              ${this.showSearchButtonText
                ? html`<span>${msg('Search', {desc: 'Search button'})}</span>`
                : nothing}
            </div>
          </searchalicious-button>
        </div>
        ${this.canReset
          ? html`<searchalicious-button-transparent @click=${this.onReset}
              >${msg('Reset')}</searchalicious-button-transparent
            >`
          : nothing}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-bar': SearchaliciousBar;
  }
}
