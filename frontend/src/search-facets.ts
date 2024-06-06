import {LitElement, html, nothing, css} from 'lit';
import {customElement, property, queryAssignedNodes} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';
import {SearchaliciousResultCtlMixin} from './mixins/search-results-ctl';
import {SearchResultEvent} from './events';
import {DebounceMixin} from './mixins/debounce';

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
export class SearchaliciousFacets extends SearchaliciousResultCtlMixin(
  LitElement
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

  override render() {
    // we always want to render slot, baceauso we use queryAssignedNodes
    // but we may not want to display them
    const display = this.facets ? '' : 'display: none';
    return html`<div part="facets" style="${display}"><slot></slot></div> `;
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
export class SearchaliciousTermsFacet extends DebounceMixin(
  SearchaliciousFacet
) {
  static override styles = css`
    .term-wrapper {
      display: block;
    }
  `;

  @property({attribute: false})
  selectedTerms: PresenceInfo = {};

  @property({attribute: false, type: Array})
  customTerms: string[] = [];

  /**
   * Set wether a term is selected or not
   */
  setTermSelected(e: Event) {
    const element = e.target as HTMLInputElement;
    const name = element.name;
    if (element.checked) {
      this.selectedTerms[name] = true;
    } else {
      delete this.selectedTerms[name];
    }
  }

  addTerm(event: CustomEvent) {
    const value = event.detail.value;
    if (this.customTerms.includes(value)) return;
    this.customTerms = [...this.customTerms, value];
    this.selectedTerms[value] = true;
  }

  /**
   * Create the search term based upon the selected terms
   */
  override searchFilter(): string | undefined {
    let values = Object.keys(this.selectedTerms);
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

  searchTerm(value: string) {
    // TODO search terms
    console.log(`${value} with facet ${this.name}`);
  }

  onInputAddTerm(event: CustomEvent) {
    const value = event.detail.value;
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    this.debounce(() => {
      this.searchTerm(value);
    });
  }

  /**
   * Render a field to add a term
   */
  renderAddTerm() {
    const inputName = `add-term-for-${this.name}`;
    const options = ['test', 'lol'];
    return html`
      <div class="add-term" part="add-term">
        <label for="${inputName}">Other</label>
        <searchalicious-autocomplete
          .inputName=${inputName}
          .options=${options}
          @autocomplete-submit=${this.addTerm}
          @autocomplete-input=${this.onInputAddTerm}
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
        <input
          type="checkbox"
          name="${term.key}"
          ?checked=${this.selectedTerms[term.key]}
          @change=${this.setTermSelected}
        /><label for="${term.key}"
          >${term.name}
          ${term.count
            ? html`<span part="docCount">(${term.count})</span>`
            : nothing}</label
        >
      </div>
    `;
  }

  /**
   * Renders the facet content
   */
  override renderFacet() {
    const items = (this.infos!.items || []) as FacetTerm[];
    return html`
      <fieldset name=${this.name}>
        <!-- FIXME: translate -->
        <legend>${this.name}</legend>
        ${repeat(
          items,
          (item: FacetTerm) => `${item.key}-${item.count}`,
          (item: FacetTerm) => this.renderTerm(item)
        )}
        --- ${this.customTerms.join(', ')} ---
        ${items.length ? this.renderAddTerm() : ''}
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
