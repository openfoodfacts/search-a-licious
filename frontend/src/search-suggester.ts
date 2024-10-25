/**
 * Search suggester is an element that should be placed inside a search-bar component.
 * It indicates some suggestion that the search bar should apply
 *
 */
import {LitElement, TemplateResult, html} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {SearchaliciousTermsMixin} from './mixins/suggestions-ctl';
import {SearchaliciousSearchInterface} from './mixins/search-ctl';
import {SuggestionSelectionOption} from './mixins/suggestion-selection';
import {SearchaliciousFacets} from './search-facets';
import {removeLangFromTermId} from './utils/taxonomies';

/**
 * Type for a suggested option
 */
export type SuggestOption = SuggestionSelectionOption & {
  /**
   * source of this suggestion
   */
  source: SearchaliciousSuggester;
};

export class SearchaliciousSuggester extends LitElement {
  /**
   * Query for options to suggest for value and return them
   */
  async getSuggestions(_value: string): Promise<SuggestOption[]> {
    throw new Error('Not implemented, implement in child class');
  }

  /**
   * Select a suggestion
   */
  async selectSuggestion(_selected: SuggestionSelectionOption) {
    throw new Error('Not implemented, implement in child class');
  }

  /**
   * Render a suggestion
   */
  renderSuggestion(_suggestion: SuggestOption, _index: number): TemplateResult {
    throw new Error('Not implemented, implement in child class');
  }
}

/**
 * An element to be used inside a searchalicious-bar component.
 * It enables giving suggestions that are based upon taxonomies
 */
@customElement('searchalicious-taxonomy-suggester')
export class SearchaliciousTaxonomySuggester extends SearchaliciousTermsMixin(
  SearchaliciousSuggester
) {
  // TODO: suggestion should be by type
  // for that we need for example to use slot by taxonomy where we put the value
  // this would enable adding beautiful html selections

  /**
   * Taxonomies we want to use for suggestions
   */
  @property({type: String, attribute: 'taxonomies'})
  taxonomies = '';

  /**
   * Fuzziness level for suggestions
   */
  @property({type: Number})
  fuzziness = 2;

  /**
   * taxonomies attribute but as an array of String
   */
  get taxonomiesList() {
    return this.taxonomies.split(',');
  }

  /**
   * Return the search bar this element is contained in
   */
  get searchBar(): SearchaliciousSearchInterface {
    const searchBar = this.closest('searchalicious-bar');
    if (searchBar == null) {
      throw new Error(
        'Taxonomy suggester must be contained in a searchalicious-bar'
      );
    }
    return searchBar;
  }

  /** list of facets containers */
  _facetsParentNode() {
    return document.querySelectorAll(
      `searchalicious-facets[search-name=${this.searchBar.name}]`
    );
  }

  /**
   * Select a term by taxonomy in all facets
   * It will update the selected terms in facets
   * @param taxonomy
   * @param term
   */
  selectTermByTaxonomy(taxonomy: string, term: string) {
    for (const facets of this._facetsParentNode()) {
      // if true, the facets has been updated
      if (
        (facets as SearchaliciousFacets).selectTermByTaxonomy(taxonomy, term)
      ) {
        return;
      }
    }
    // TODO: handle the case of no facet found: replace expression with a condition on specific field
  }

  /**
   * Query for options to suggest
   */
  override async getSuggestions(value: string): Promise<SuggestOption[]> {
    return this.getTaxonomiesTerms(value, this.taxonomiesList).then(() => {
      return this.terms.map((term) => ({
        value: removeLangFromTermId(term.id),
        label: term.text,
        id: term.taxonomy_name + '-' + term.id,
        source: this,
        input: value,
      }));
    });
  }

  override async selectSuggestion(selected: SuggestionSelectionOption) {
    this.selectTermByTaxonomy(this.taxonomies, selected.value);
  }

  override renderSuggestion(
    suggestion: SuggestOption,
    _index: number
  ): TemplateResult {
    return html`<searchalicious-suggestion-entry
      .term=${suggestion}
    ></searchalicious-suggestion-entry>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-taxonomy-suggest': SearchaliciousTaxonomySuggester;
  }
}

/**
 * An expression to be able to get all suggesters using a querySelectorAll
 */
export const SuggestersSelector = 'searchalicious-taxonomy-suggest';
