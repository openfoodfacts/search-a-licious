/**
 * Search suggester is an element that should be placed inside a search-bar component.
 * It indicates some suggestion that the search bar should apply
 *
 */
import {LitElement, PropertyValues, TemplateResult, html} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {consume} from '@lit/context';
import {SearchaliciousTermsMixin} from './mixins/suggestions-ctl';
import {SearchaliciousSearchInterface} from './interfaces/search-ctl-interfaces';
import {
  SuggestionSelectionOption,
  SuggestOption,
} from './interfaces/suggestion-interfaces';
import {
  SuggesterRegistryInterface,
  suggesterRegistryContext,
} from './interfaces/search-bar-interfaces';
import {SearchaliciousFacetsInterface} from './interfaces/facets-interfaces';
import {removeLangFromTermId} from './utils/taxonomies';
//import {Constructor} from './mixins/utils';

export class SearchaliciousSuggester extends LitElement {
  //suggesterRegistry: SuggesterRegistryInterface;

  //constructor(suggesterRegistry: SuggesterRegistryInterface) {
  //  super();
  //  this.suggesterRegistry = suggesterRegistry;
  //}

  @consume({context: suggesterRegistryContext})
  suggesterRegistry!: SuggesterRegistryInterface;

  //override connectedCallback() {
  //  super.connectedCallback();
  //  // this is the good time to register
  //  this.suggesterRegistry?.registerSuggester(this);
  //}

  override firstUpdated(changedProperties: PropertyValues<this>) {
    super.firstUpdated(changedProperties);
    // this is the good time to register
    this.suggesterRegistry?.registerSuggester(this);
  }

  // override render() {
  //   this.suggesterRegistry?.registerSuggester(this);
  //   return html``;
  // }

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
    for (const facets of this.suggesterRegistry.searchCtl!.relatedFacets()) {
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
//export const SuggestersToClass: Record<
//  string,
//  Constructor<SearchaliciousSuggester>
//> = {
//  'searchalicious-taxonomy-suggest': SearchaliciousTaxonomySuggester,
//};

export class SuggesterRegistry implements SuggesterRegistryInterface {
  suggesters: SearchaliciousSuggester[];
  searchCtl: SearchaliciousSearchInterface;

  constructor(searchCtl: SearchaliciousSearchInterface) {
    this.searchCtl = searchCtl;
    this.suggesters = [];
  }

  registerSuggester(suggester: SearchaliciousSuggester): void {
    if (!this.suggesters.includes(suggester)) {
      this.suggesters.push(suggester);
    }
  }
}
