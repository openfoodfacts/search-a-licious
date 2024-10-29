/**
 * Search suggester is an element that should be placed inside a search-bar component.
 * It indicates some suggestion that the search bar should apply
 *
 */
import {LitElement, TemplateResult, html} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {SearchaliciousTermsMixin} from './mixins/suggestions-ctl';
import {SearchaliciousSearchInterface} from './interfaces/search-ctl-interfaces';
import {
  SuggestionSelectionOption,
  SuggestOption,
} from './interfaces/suggestion-interfaces';
import {SearchaliciousFacetsInterface} from './interfaces/facets-interfaces';
import {removeLangFromTermId} from './utils/taxonomies';

export class SearchaliciousSuggester extends LitElement {
  @property({attribute: false})
  searchCtl: SearchaliciousSearchInterface | undefined;

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

type taxonomySelectionOption = SuggestionSelectionOption & {
  /**
   * taxonomy related to this suggestion
   */
  taxonomy: string;
};

/**
 * An element to be used inside a searchalicious-bar component.
 * It enables giving suggestions that are based upon taxonomies
 */
@customElement('searchalicious-taxonomy-suggest')
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
   * Select a term by taxonomy in all facets
   * It will update the selected terms in facets
   * @param taxonomy
   * @param term
   */
  selectTermByTaxonomy(taxonomy: string, term: string) {
    for (const facets of this.searchCtl!.relatedFacets()) {
      // if true, the facets has been updated
      if (
        (facets as SearchaliciousFacetsInterface).selectTermByTaxonomy(
          taxonomy,
          term
        )
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
        taxonomy: term.taxonomy_name,
      }));
    });
  }

  override async selectSuggestion(selected: SuggestionSelectionOption) {
    this.selectTermByTaxonomy(
      (selected as taxonomySelectionOption).taxonomy,
      selected.value
    );
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
