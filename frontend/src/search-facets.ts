import {LitElement, html, css} from 'lit';
import {customElement, property, queryAssignedNodes} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';

import {SearchaliciousResultCtlMixin} from './search-results-ctl';
import {SearchResultEvent} from './events';
import keys from 'lodash-es/keys';

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
      return html``; // FIXME: is this ok ?
    }
  }
}

/**
 * This is a "terms" facet, this must be within a searchalicious-facets element
 */
@customElement('searchalicious-facet-terms')
export class SearchaliciousTermsFacet extends SearchaliciousFacet {
  static override styles = css`
    .term-wrapper {
      display: block;
    }
  `;

  @property({attribute: false})
  selectedTerms: PresenceInfo = {};

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

  /**
   * Create the search term based upon the selected terms
   */
  override searchFilter(): string | undefined {
    const values = keys(this.selectedTerms) as String[];
    if (values.length === 0) {
      return undefined;
    }
    let orValues = values.join(' OR ');
    if (values.length > 1) {
      orValues = `(${orValues})`;
    }
    return `${this.name}:${orValues}`;
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
          >${term.name} <span part="docCount">(${term.count})</span></label
        >
      </div>
    `;
  }

  /**
   * Renders the facet content
   */
  override renderFacet() {
    return html`
      <fieldset name=${this.name}>
        <!-- FIXME: translate -->
        <legend>${this.name}</legend>
        ${repeat(
          (this.infos!.items || []) as FacetTerm[],
          (item: FacetTerm) => `${item.key}-${item.count}`,
          (item: FacetTerm) => this.renderTerm(item)
        )}
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
