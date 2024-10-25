import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {SearchaliciousSearchMixin} from './mixins/search-ctl';
import {localized, msg} from '@lit/localize';
import {setLocale} from './localization/main';
import {SuggestionSelectionMixin} from './mixins/suggestion-selection';
import {
  SearchaliciousSuggester,
  SuggestOption,
  SuggestersSelector,
} from './search-suggester';
import {classMap} from 'lit/directives/class-map.js';
import {searchBarInputAndButtonStyle} from './css/header';
import {SearchaliciousEvents} from './utils/enums';
import {isTheSameSearchName} from './utils/search';

/**
 * The search bar element
 *
 * This is the main component, it will enable the input of the search query
 * and it also manage all the search thanks to SearchaliciousSearchMixin inheritance.
 */
@customElement('searchalicious-bar')
@localized()
export class SearchaliciousBar extends SuggestionSelectionMixin(
  SearchaliciousSearchMixin(LitElement)
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
        top: 100%;
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

      .search-input {
        padding-left: 0.5rem;
        padding-right: 0.5rem;
      }
    `,
  ];

  /**
   * The options for the suggestion.
   *
   * We redefine them to use SuggestOption
   */
  @property({attribute: false, type: Array})
  override options: SuggestOption[] = [];
  /**
   * Placeholder attribute is stored in a private variable to be able to use the msg() function
   * it stores the placeholder attribute value if it is set
   * @private
   */
  private _placeholder?: string;

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

  constructor() {
    super();

    // allow to set the locale from the browser
    // @ts-ignore
    window.setLocale = setLocale;
  }

  /** Return the list of suggesters contained in the search bar */
  get suggesters() {
    const suggesters: SearchaliciousSuggester[] = [];
    this.querySelectorAll(SuggestersSelector).forEach((element) => {
      suggesters.push(element as SearchaliciousSuggester);
    });
    return suggesters;
  }

  /** Ask suggesters for suggested options */
  async getSuggestions(value: string) {
    return Promise.allSettled(
      this.suggesters.map((suggester) => {
        return suggester.getSuggestions(value);
      })
    ).then((optionsLists) => {
      const options: SuggestOption[] = [];
      optionsLists.forEach((result) => {
        if (result.status === 'fulfilled' && result.value != null) {
          options.push(...(result.value as SuggestOption[]));
        }
      });
      return options;
    });
  }

  /**
   * Handle the input event
   * It will update the query and call the getTaxonomiesTerms method to show suggestions
   * @param value
   */
  override handleInput(value: string) {
    this.query = value;

    this.updateSearchSignals();
    this.debounce(() => {
      this.getSuggestions(value).then((options) => {
        this.options = options;
      });
    });
  }

  /**
   * Submit - might either be selecting a suggestion or submitting a search expression
   */
  override submitSuggestion(isSuggestion?: boolean) {
    // If the value is a suggestion, select the term and reset the input otherwise search
    if (isSuggestion) {
      const selectedOption = this.selectedOption as SuggestOption;
      selectedOption!.source.selectSuggestion(selectedOption);
      this.resetInput(this.selectedOption);
      this.query = ''; // not sure if we should instead put the value of remaining input
    } else {
      this.query = this.selectedOption?.value || '';
      this.blurInput();
    }
    this.search();
  }

  /**
   * Render the suggestions when the input is focused and the value is not empty
   */
  renderSuggestions() {
    // Don't show suggestions if the input is not focused or the value is empty or there are no suggestions
    if (!this.visible || !this.selectedOption || this.options.length === 0) {
      return html``;
    }

    return html`
      <ul>
        ${this.options.map(
          (option, index) => html`
            <li
              class=${classMap({selected: index + 1 === this.currentIndex})}
              @click=${this.onClick(option)}
            >
              ${option.source.renderSuggestion(option, index)}
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

  override connectedCallback() {
    super.connectedCallback();

    this.addEventHandler(SearchaliciousEvents.RESET_SEARCH, (event: Event) => {
      if (isTheSameSearchName(this.name, event)) {
        this.onReset();
      }
    });
  }

  override disconnectedCallback() {
    super.disconnectedCallback();

    this.removeEventHandler(
      SearchaliciousEvents.RESET_SEARCH,
      (event: Event) => {
        if (isTheSameSearchName(this.name, event)) {
          this.onReset();
        }
      }
    );
  }
  override render() {
    return html`
      <div class="search-bar" part="wrapper">
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
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-bar': SearchaliciousBar;
  }
}
