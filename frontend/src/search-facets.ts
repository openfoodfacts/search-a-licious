import {LitElement, html, nothing, css} from 'lit';
import {customElement, property, queryAssignedNodes} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';
import {SearchaliciousResultCtlMixin} from './mixins/search-results-ctl';
import {SearchResultEvent} from './events';
import {DebounceMixin} from './mixins/debounce';
import {SearchaliciousTermsMixin} from './mixins/suggestions-ctl';
import {getTaxonomyName, removeLangFromTermId} from './utils/taxonomies';
import {SearchActionMixin} from './mixins/search-action';
import {FACET_TERM_OTHER} from './utils/constants';
import {QueryOperator} from './utils/enums';
import {getPluralTranslation} from './localization/translations';
import {msg, localized} from '@lit/localize';
import {WHITE_PANEL_STYLE} from './styles';

interface FacetsInfos {
  [key: string]: FacetInfo;
}

interface FacetInfo {
  name: string;
  // TODO: add other types if needed
  items: FacetItem[];
}

interface FacetItem {
  key: string;
  name: string;
}

interface FacetTerm extends FacetItem {
  count: number;
}

interface PresenceInfo {
  [index: string]: boolean;
}

function stringGuard(s: string | undefined): s is string {
  return s != null;
}

/**
 * Parent Component to display a side search filter (aka facets).
 *
 * It must contains a SearchaliciousFacet component for each facet we want to display.
 */
@customElement('searchalicious-facets')
@localized()
export class SearchaliciousFacets extends SearchActionMixin(
  SearchaliciousResultCtlMixin(LitElement)
) {
  static override styles = css`
    .reset-button-wrapper {
      display: flex;
      align-items: center;
      justify-content: center;
    }
  `;
  // the last search facets
  @property({attribute: false})
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  facets?: FacetsInfos;

  @queryAssignedNodes({flatten: true})
  slotNodes!: Array<Node>;

  _facetNodes(): SearchaliciousFacet[] {
    return this.slotNodes.filter(
      (node) => node instanceof SearchaliciousFacet
    ) as SearchaliciousFacet[];
  }

  setSelectedTermsByFacet(selectedTermsByFacet: Record<string, string[]>) {
    this._facetNodes().forEach((node) => {
      node.setSelectedTerms(selectedTermsByFacet[node.name]);
    });
  }

  /**
   * Get a facet node by its taxonomy
   * It will return undefined if the taxonomy is not found
   * @param taxonomy
   */
  getFacetNodeByTaxonomy(taxonomy: string): SearchaliciousFacet | undefined {
    return this._facetNodes().find((node) => node.taxonomy === taxonomy);
  }

  /**
   * Select a term by its taxonomy and term name
   * It will return false if the taxonomy is not found
   * @param taxonomy
   * @param term
   */
  selectTermByTaxonomy(taxonomy: string, term: string): boolean {
    const node = this.getFacetNodeByTaxonomy(taxonomy);
    if (!node) {
      return false;
    }
    node.setTermSelected(true, term);
    return true;
  }

  /**
   * Names of facets we need to query,
   * this is the names of contained facetNodes.
   *
   * This is used by search-ctl to build the query
   */
  getFacetsNames(): string[] {
    return this._facetNodes().map((node) => node.name);
  }

  getSearchFilters(): string[] {
    return this._facetNodes()
      .map((node) => node.searchFilter())
      .filter(stringGuard);
  }

  setSelectedTerms(terms: string[]) {
    this._facetNodes().forEach((node) => {
      node.setSelectedTerms(terms);
    });
  }

  /**
   * As a result is received, we dispatch facets values to facetNodes
   * @param event search result event
   */
  override handleResults(event: SearchResultEvent) {
    this.facets = event.detail.facets as FacetsInfos;
    if (this.facets) {
      // dispatch to children
      this._facetNodes().forEach((node) => {
        node.infos = this.facets![node.name];
      });
    }
  }

  reset = () => {
    this._facetNodes().forEach((node) => {
      node.reset(false);
    });
    this._launchSearch();
  };

  override render() {
    // we always want to render slot, baceauso we use queryAssignedNodes
    // but we may not want to display them
    const display = this.facets ? '' : 'display: none';
    return html`<div part="facets" style="${display}">
      <slot></slot>
      <div class="reset-button-wrapper">
        <searchalicious-secondary-button @click=${this.reset}
          >${msg('Reset filters')}</searchalicious-secondary-button
        >
      </div>
    </div> `;
  }
}

/**
 * Base Component to display a side search filter (aka facets)
 *
 * This is a base class, implementations are specific based on facet type
 */
export class SearchaliciousFacet extends LitElement {
  /**
   * The name of the facet we display
   */
  @property()
  name = '';

  // the last search infor for my facet
  @property({attribute: false})
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  infos?: FacetInfo;

  /**
   * Get the name of the taxonomy from the facet name
   */
  get taxonomy(): string {
    return getTaxonomyName(this.name);
  }

  setTermSelected(checked: boolean, name: string) {
    throw new Error(
      `setTermSelected not implemented: implement in sub class with checked ${checked} and name ${name}`
    );
  }

  renderFacet() {
    throw new Error('renderFacet not implemented: implement in sub class');
  }

  searchFilter(): string | undefined {
    throw new Error('renderFacet not implemented: implement in sub class');
  }

  reset = (submit?: boolean): void => {
    throw new Error(
      `reset not implemented: implement in sub class with submit ${submit}`
    );
  };
  setSelectedTerms(terms: string[]) {
    throw new Error(
      `setSelectedTerms not implemented: implement in sub class ${terms.join(
        ', '
      )}`
    );
  }

  override render() {
    if (this.infos) {
      return this.renderFacet();
    } else {
      return html``;
    }
  }
}

/**
 * This is a "terms" facet, this must be within a searchalicious-facets element
 */
@customElement('searchalicious-facet-terms')
@localized()
export class SearchaliciousTermsFacet extends SearchActionMixin(
  SearchaliciousTermsMixin(DebounceMixin(SearchaliciousFacet))
) {
  static override styles = [
    WHITE_PANEL_STYLE,
    css`
      fieldset {
        margin-top: 1rem;
        border: none;
      }
      .button {
        margin-left: auto;
        margin-right: auto;
      }
      .legend-wrapper {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        flex-wrap: wrap;
        max-width: 100%;
      }
      [part='button-transparent'] {
        --button-transparent-padding: 0.5rem 1rem;
      }
      .add-term {
        display: flex;
        flex-direction: column;
      }
    `,
  ];

  @property({
    attribute: false,
    type: Object,
  })
  selectedTerms: PresenceInfo = {};

  // Will be usefull if we want to display term without searching
  @property({attribute: false, type: Array})
  autocompleteTerms: string[] = [];

  @property({attribute: 'search-name'})
  override searchName = 'off';

  @property({attribute: 'show-other', type: Boolean})
  showOther = false;

  _launchSearchWithDebounce = () =>
    this.debounce(() => {
      this._launchSearch();
    });
  /**
   * Set wether a term is selected or not
   */
  override setTermSelected(checked: boolean, name: string) {
    this.selectedTerms = {
      ...this.selectedTerms,
      ...{[name]: checked},
    };
  }

  addTerm(event: CustomEvent) {
    const value = event.detail.value;
    if (this.autocompleteTerms.includes(value)) return;
    this.autocompleteTerms = [...this.autocompleteTerms, value];
    this.selectedTerms[value] = true;
    // Launch search so that filters will be automatically refreshed
    this._launchSearchWithDebounce();
  }

  /**
   * Set the selected terms from an array of terms
   * This is used to restore the state of the facet
   * @param terms
   */
  override setSelectedTerms(terms?: string[]) {
    this.selectedTerms = {};
    for (const term of terms ?? []) {
      this.selectedTerms[term] = true;
    }
  }

  /**
   * Create the search term based upon the selected terms
   */
  override searchFilter(): string | undefined {
    let values = Object.keys(this.selectedTerms).filter(
      (key) => this.selectedTerms[key]
    );
    // add quotes if we have ":" in values
    values = values.map((value) =>
      value.includes(':') ? `"${value}"` : value
    );
    if (values.length === 0) {
      return undefined;
    }
    let orValues = values.join(QueryOperator.OR);
    if (values.length > 1) {
      orValues = `(${orValues})`;
    }
    return `${this.name}:${orValues}`;
  }

  /**
   * Handle the autocomplete-input event on the add term input
   * get the terms for the taxonomy
   * @param event
   * @param taxonomy
   */
  onInputAddTerm(event: CustomEvent, taxonomy: string) {
    const value = event.detail.value;
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    this.debounce(() => {
      // update options in terms SearchaliciousTermsMixin
      // which will update the property of the autocomplete component during render
      this.getTaxonomiesTerms(value, [taxonomy]);
    }, 500);
  }

  /**
   * Renders the add term input when showOther is true
   */
  renderAddTerm() {
    const inputName = `add-term-for-${this.name}`;
    const taxonomy = getTaxonomyName(this.name);
    const otherItem = this.infos!.items?.find(
      (item) => item.key === FACET_TERM_OTHER
    ) as FacetTerm | undefined;
    const onInput = (e: CustomEvent) => {
      this.onInputAddTerm(e, taxonomy);
    };

    const options = (this.terms || []).map((term) => {
      return {
        value: removeLangFromTermId(term.id),
        label: term.text,
      };
    });

    return html`
      <div class="add-term" part="add-term">
        <label for="${inputName}"
          >${getPluralTranslation(
            otherItem?.count,
            msg('Other'),
            msg('Others')
          )}
          ${otherItem?.count ? `(${otherItem.count})` : nothing}</label
        >
        <searchalicious-autocomplete
          .inputName=${inputName}
          .options=${options}
          .isLoading=${this.isTermsLoading}
          @searchalicious-autocomplete-submit=${this.addTerm}
          @searchalicious-autocomplete-input=${onInput}
        ></searchalicious-autocomplete>
      </div>
    `;
  }

  /**
   * Handle the checkbox change event
   * It will select or unselect term
   * @param detail
   */
  onCheckboxChange({detail}: {detail: {checked: boolean; name: string}}) {
    this.setTermSelected(detail.checked, detail.name);
  }

  /**
   * Renders a single term
   */
  renderTerm(term: FacetTerm) {
    return html`
      <div>
        <searchalicious-checkbox
          .name=${term.key}
          .checked=${this.selectedTerms[term.key]}
          @change=${this.onCheckboxChange}
        >
          <!--     "display: contents;" is used to avoid the wrapping of the span in a div cf https://lit.dev/docs/frameworks/react/#using-slots -->
          <div slot="label" style="display: contents;">
            ${term.name}
            ${term.count
              ? html`<span part="docCount">(${term.count})</span>`
              : nothing}
          </div>
        </searchalicious-checkbox>
      </div>
    `;
  }

  /**
   * Reset the selected terms and launch a search
   * @param search
   */
  override reset = (search = true) => {
    Object.keys(this.selectedTerms).forEach((key) => {
      this.selectedTerms[key] = false;
    });
    this.autocompleteTerms = [];
    this.requestUpdate('selectedTerms');
    search && this._launchSearchWithDebounce();
  };

  /**
   * Renders the facet content
   */
  override renderFacet() {
    const items = (this.infos!.items || []).filter(
      (item) => !this.showOther || item.key !== FACET_TERM_OTHER
    ) as FacetTerm[];

    return html`
      <fieldset name=${this.name} class="white-panel">
        <!-- FIXME: translate -->
        <div class="legend-wrapper">
          <!-- Allow to customize the legend -->
          <legend><slot name="legend">${this.name}</slot></legend>
          <span class="buttons">
            <searchalicious-button-transparent
                title="Reset ${this.name}"
              @click=${this.reset}
              >
                <searchalicious-icon-cross></searchalicious-icon-cross
            </searchalicious-button-transparent
            >
          </span>
        </div>
        ${repeat(
          items,
          (item: FacetTerm) => `${item.key}-${item.count}`,
          (item: FacetTerm) => this.renderTerm(item)
        )}
        ${this.showOther && items.length ? this.renderAddTerm() : nothing}
      </fieldset>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-facets': SearchaliciousFacets;
    'searchalicious-facet-terms': SearchaliciousTermsFacet;
  }
}
