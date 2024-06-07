import {LitElement, html, nothing, css} from 'lit';
import {customElement, property, queryAssignedNodes} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';
import {SearchaliciousResultCtlMixin} from './mixins/search-results-ctl';
import {SearchResultEvent} from './events';
import {DebounceMixin} from './mixins/debounce';
import {SearchaliciousTermsMixin} from './mixins/taxonomies-ctl';
import {getTaxonomyName} from './utils/taxonomies';
import {SearchActionMixin} from './mixins/search-action';
import {FACET_TERM_OTHER} from './utils/constants';
import {CheckboxMixin} from './mixins/checkbox';

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
export class SearchaliciousFacets extends SearchActionMixin(
  SearchaliciousResultCtlMixin(LitElement)
) {
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
      <div>
        <searchalicious-reset-button
          @reset=${this.reset}
        ></searchalicious-reset-button>
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
export class SearchaliciousTermsFacet extends CheckboxMixin(
  SearchActionMixin(
    SearchaliciousTermsMixin(DebounceMixin(SearchaliciousFacet))
  )
) {
  static override styles = css`
    .term-wrapper {
      display: block;
    }
    .button {
      margin-left: auto;
      margin-right: auto;
    }
  `;

  @property({
    attribute: false,
    type: Object,
  })
  selectedTerms: PresenceInfo = {};

  @property({attribute: false, type: Array})
  customTerms: string[] = [];

  @property({attribute: 'search-name'})
  override searchName = 'off';

  @property({attribute: 'show-other', type: Boolean})
  showOther = true;

  _launchSearchWithDebounce = () =>
    this.debounce(() => {
      this._launchSearch();
    });
  /**
   * Set wether a term is selected or not
   */
  setTermSelected({detail}: {detail: {checked: boolean; name: string}}) {
    if (detail.checked) {
      this.selectedTerms[detail.name] = true;
    } else {
      this.selectedTerms[detail.name] = false;
    }
  }

  addTerm(event: CustomEvent) {
    const value = event.detail.value;
    if (this.customTerms.includes(value)) return;
    this.customTerms = [...this.customTerms, value];
    this.selectedTerms[value] = true;
    this._launchSearchWithDebounce();
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
    let orValues = values.join(' OR ');
    if (values.length > 1) {
      orValues = `(${orValues})`;
    }
    return `${this.name}:${orValues}`;
  }

  onInputAddTerm(event: CustomEvent, taxonomy: string) {
    const value = event.detail.value;
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    this.debounce(() => {
      this.getTaxonomiesTerms(value, [taxonomy]);
    });
  }

  /**
   * Render a field to add a term
   */
  renderAddTerm(otherItem?: FacetTerm) {
    const inputName = `add-term-for-${this.name}`;
    const taxonomy = getTaxonomyName(this.name);
    const onInput = (e: CustomEvent) => {
      this.onInputAddTerm(e, taxonomy);
    };

    const options = (this.termsByTaxonomyId[taxonomy] || []).map((term) => {
      return {
        value: term.id.replace(/^en:/, ''),
        label: term.text,
      };
    });

    return html`
      <div class="add-term" part="add-term">
        <label for="${inputName}"
          >Other ${otherItem?.count ? `(${otherItem.count})` : nothing}</label
        >
        <searchalicious-autocomplete
          .inputName=${inputName}
          .options=${options}
          .isLoading=${this.loadingByTaxonomyId[taxonomy]}
          @autocomplete-submit=${this.addTerm}
          @autocomplete-input=${onInput}
        ></searchalicious-autocomplete>
      </div>
    `;
  }

  /**
   * Renders a single term
   */
  renderTerm(term: FacetTerm) {
    return html`
      <div class="term-wrapper" part="term-wrapper">
        <searchalicious-checkbox
          .name=${term.key}
          .checked=${this.selectedTerms[term.key]}
          @change=${this.setTermSelected}
        ></searchalicious-checkbox>
        <label for="${term.key}"
          >${term.name}
          ${term.count
            ? html`<span part="docCount">(${term.count})</span>`
            : nothing}</label
        >
      </div>
    `;
  }

  override reset = (search = true) => {
    Object.keys(this.selectedTerms).forEach((key) => {
      this.selectedTerms[key] = false;
    });
    this.customTerms = [];
    this.refreshCheckboxes();
    search && this._launchSearchWithDebounce();
  };
  _renderResetButton() {
    return html`
      <div>
        <searchalicious-reset-button
          @reset=${this.reset}
        ></searchalicious-reset-button>
      </div>
    `;
  }

  /**
   * Renders the facet content
   */
  override renderFacet() {
    const items = (this.infos!.items || []).filter(
      (item) => item.key !== FACET_TERM_OTHER
    ) as FacetTerm[];
    const otherItem = this.infos!.items?.find(
      (item) => item.key === FACET_TERM_OTHER
    ) as FacetTerm | undefined;

    return html`
      <fieldset name=${this.name}>
        <!-- FIXME: translate -->
        <legend>${this.name}</legend>
        ${repeat(
          items,
          (item: FacetTerm) => `${item.key}-${item.count}`,
          (item: FacetTerm) => this.renderTerm(item)
        )}
        ${this.customTerms.join(', ')}
        ${this.showOther && items.length
          ? this.renderAddTerm(otherItem)
          : nothing}
        ${this._renderResetButton()}
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
