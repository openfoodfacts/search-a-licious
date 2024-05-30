import {LitElement, html, css} from 'lit';
import {customElement, property, queryAssignedNodes} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';

import {SearchaliciousResultCtlMixin} from './search-results-ctl';
import {SearchResultEvent} from './events';

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

/**
 * Parent Component to display a side search filter (aka facets)
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
  facetNodes!: Array<Node>;

  /**
   * Names of facets we need to query,
   * this is the names of contained facets
   */
  getFacetsNames(): string[] {
    const _facets: string[] = [];
    this.facetNodes.forEach((node) => {
      if (node instanceof SearchaliciousFacet) {
        _facets.push(node.name);
      }
    });
    return _facets;
  }

  override handleResults(event: SearchResultEvent) {
    this.facets = event.detail.facets as FacetsInfos;
    if (this.facets) {
      // dispatch to children
      this.facetNodes.forEach((node) => {
        if (node instanceof SearchaliciousFacet) {
          node.infos = this.facets![node.name];
        }
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
  @property()
  name = '';

  // the last search infor for my facet
  @property({attribute: false})
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  infos?: FacetInfo;

  renderFacet() {
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

@customElement('searchalicious-facet-terms')
export class SearchaliciousTermsFacet extends SearchaliciousFacet {
  static override styles = css`
    .term-wrapper {
      display: block;
    }
  `;
  renderTerm(term: FacetTerm) {
    return html`
      <div class="term-wrapper" part="term-wrapper">
        <input type="checkbox" name="${term.key}" /><label for="${term.key}"
          >${term.name} <span part="docCount">(${term.count})</span></label
        >
      </div>
    `;
  }

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

/*

things to add to API:
1. selected filters (if easy) --> we put it in a specific but we can match
2. widget type to use for each facet --> may also be separate to simplify ?
3. translations of filter names

{
	"aggregations": {
		"nova_groups": {
			"doc_count_error_upper_bound": 0,
			"sum_other_doc_count": 0,
			"buckets": [
				{
					"key": "4",
					"doc_count": 559
				},
				{
					"key": "3",
					"doc_count": 158
				},
				{
					"key": "1",
					"doc_count": 95
				},
				{
					"key": "2",
					"doc_count": 50
				}
			]
		},
		"owner": {
			"doc_count_error_upper_bound": 0,
			"sum_other_doc_count": 21,
			"buckets": [
				{
					"key": "org-carrefour",
					"doc_count": 9
				},
				{
					"key": "org-systeme-u",
					"doc_count": 9
				},
				{
					"key": "org-les-mousquetaires",
					"doc_count": 6
				},
				{
					"key": "org-idiffusion",
					"doc_count": 5
				},
				{
					"key": "org-scamark",
					"doc_count": 5
				},
				{
					"key": "org-auchan-apaw",
					"doc_count": 4
				},
				{
					"key": "org-casino",
					"doc_count": 3
				},
				{
					"key": "org-groupe-ldc",
					"doc_count": 3
				},
				{
					"key": "org-albert-menes",
					"doc_count": 2
				},
				{
					"key": "org-alnatura",
					"doc_count": 2
				}
			]
		},
		"categories_tags": {
			"doc_count_error_upper_bound": 58,
			"sum_other_doc_count": 5438,
			"buckets": [
				{
					"key": "en:plant-based-foods-and-beverages",
					"doc_count": 419
				},
				{
					"key": "en:plant-based-foods",
					"doc_count": 367
				},
				{
					"key": "en:snacks",
					"doc_count": 266
				},
				{
					"key": "en:sweet-snacks",
					"doc_count": 202
				},
				{
					"key": "en:dairies",
					"doc_count": 163
				},
				{
					"key": "en:beverages",
					"doc_count": 143
				},
				{
					"key": "en:fermented-foods",
					"doc_count": 127
				},
				{
					"key": "en:cereals-and-potatoes",
					"doc_count": 123
				},
				{
					"key": "en:fermented-milk-products",
					"doc_count": 123
				},
				{
					"key": "en:meats-and-their-products",
					"doc_count": 118
				}
			]
		},
		"brands_tags": {
			"doc_count_error_upper_bound": 8,
			"sum_other_doc_count": 1759,
			"buckets": [
				{
					"key": "bonarea",
					"doc_count": 17
				},
				{
					"key": "carrefour",
					"doc_count": 15
				},
				{
					"key": "lidl",
					"doc_count": 15
				},
				{
					"key": "nestle",
					"doc_count": 13
				},
				{
					"key": "tesco",
					"doc_count": 13
				},
				{
					"key": "u",
					"doc_count": 13
				},
				{
					"key": "auchan",
					"doc_count": 8
				},
				{
					"key": "coop",
					"doc_count": 7
				},
				{
					"key": "hacendado",
					"doc_count": 7
				},
				{
					"key": "ferrero",
					"doc_count": 5
				}
			]
		},
		"ecoscore_grade": {
			"doc_count_error_upper_bound": 0,
			"sum_other_doc_count": 0,
			"buckets": [
				{
					"key": "unknown",
					"doc_count": 2350
				},
				{
					"key": "b",
					"doc_count": 260
				},
				{
					"key": "d",
					"doc_count": 220
				},
				{
					"key": "c",
					"doc_count": 167
				},
				{
					"key": "e",
					"doc_count": 98
				},
				{
					"key": "a",
					"doc_count": 37
				},
				{
					"key": "not-applicable",
					"doc_count": 29
				}
			]
		},
		"states_tags": {
			"doc_count_error_upper_bound": 581,
			"sum_other_doc_count": 25942,
			"buckets": [
				{
					"key": "en:to-be-completed",
					"doc_count": 3153
				},
				{
					"key": "en:characteristics-to-be-completed",
					"doc_count": 3084
				},
				{
					"key": "en:origins-to-be-completed",
					"doc_count": 3047
				},
				{
					"key": "en:packaging-code-to-be-completed",
					"doc_count": 3007
				},
				{
					"key": "en:product-name-completed",
					"doc_count": 3001
				},
				{
					"key": "en:expiration-date-to-be-completed",
					"doc_count": 2783
				},
				{
					"key": "en:packaging-to-be-completed",
					"doc_count": 2767
				},
				{
					"key": "en:photos-uploaded",
					"doc_count": 2709
				},
				{
					"key": "en:photos-to-be-validated",
					"doc_count": 2628
				},
				{
					"key": "en:packaging-photo-to-be-selected",
					"doc_count": 2620
				}
			]
		},
		"nutrition_grades": {
			"doc_count_error_upper_bound": 0,
			"sum_other_doc_count": 0,
			"buckets": [
				{
					"key": "unknown",
					"doc_count": 1991
				},
				{
					"key": "d",
					"doc_count": 314
				},
				{
					"key": "c",
					"doc_count": 246
				},
				{
					"key": "e",
					"doc_count": 206
				},
				{
					"key": "a",
					"doc_count": 173
				},
				{
					"key": "b",
					"doc_count": 169
				},
				{
					"key": "not-applicable",
					"doc_count": 62
				}
			]
		},
		"lang": {
			"doc_count_error_upper_bound": 0,
			"sum_other_doc_count": 61,
			"buckets": [
				{
					"key": "fr",
					"doc_count": 1186
				},
				{
					"key": "en",
					"doc_count": 1040
				},
				{
					"key": "es",
					"doc_count": 353
				},
				{
					"key": "it",
					"doc_count": 239
				},
				{
					"key": "de",
					"doc_count": 220
				},
				{
					"key": "nl",
					"doc_count": 17
				},
				{
					"key": "pt",
					"doc_count": 16
				},
				{
					"key": "pl",
					"doc_count": 14
				},
				{
					"key": "ru",
					"doc_count": 12
				},
				{
					"key": "cs",
					"doc_count": 11
				}
			]
		},
		"countries_tags": {
			"doc_count_error_upper_bound": 9,
			"sum_other_doc_count": 411,
			"buckets": [
				{
					"key": "en:france",
					"doc_count": 1017
				},
				{
					"key": "en:united-states",
					"doc_count": 619
				},
				{
					"key": "en:spain",
					"doc_count": 378
				},
				{
					"key": "en:germany",
					"doc_count": 273
				},
				{
					"key": "en:italy",
					"doc_count": 252
				},
				{
					"key": "en:united-kingdom",
					"doc_count": 127
				},
				{
					"key": "en:belgium",
					"doc_count": 93
				},
				{
					"key": "en:switzerland",
					"doc_count": 92
				},
				{
					"key": "en:canada",
					"doc_count": 81
				},
				{
					"key": "en:ireland",
					"doc_count": 51
				}
			]
		},
		"labels_tags": {
			"doc_count_error_upper_bound": 18,
			"sum_other_doc_count": 1172,
			"buckets": [
				{
					"key": "en:organic",
					"doc_count": 200
				},
				{
					"key": "en:no-gluten",
					"doc_count": 177
				},
				{
					"key": "en:eu-organic",
					"doc_count": 144
				},
				{
					"key": "en:green-dot",
					"doc_count": 126
				},
				{
					"key": "en:vegetarian",
					"doc_count": 115
				},
				{
					"key": "en:vegan",
					"doc_count": 104
				},
				{
					"key": "en:nutriscore",
					"doc_count": 84
				},
				{
					"key": "fr:ab-agriculture-biologique",
					"doc_count": 61
				},
				{
					"key": "en:no-preservatives",
					"doc_count": 56
				},
				{
					"key": "en:no-lactose",
					"doc_count": 40
				}
			]
		}
	}
}
*/
