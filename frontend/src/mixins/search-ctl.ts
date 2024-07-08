import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';
import {
  EventRegistrationInterface,
  EventRegistrationMixin,
} from '../event-listener-setup';
import {QueryOperator, SearchaliciousEvents} from '../utils/enums';
import {ChangePageEvent} from '../events';
import {Constructor} from './utils';
import {SearchaliciousSort, SortParameters} from '../search-sort';
import {SearchaliciousFacets} from '../search-facets';
import {setCurrentURLHistory} from '../utils/url';
import {isNullOrUndefined} from '../utils';
import {
  API_LIST_DIVIDER,
  DEFAULT_SEARCH_NAME,
  PROPERTY_LIST_DIVIDER,
} from '../utils/constants';
import {
  HistorySearchParams,
  SearchaliciousHistoryInterface,
  SearchaliciousHistoryMixin,
} from './history';
import {SearchaliciousChart} from '../search-chart';
import {
  canResetSearch,
  isSearchChanged,
  isSearchLoading,
  searchResultDetail,
} from '../signals';
import {SignalWatcher} from '@lit-labs/preact-signals';
import {isTheSameSearchName} from '../utils/search';

export interface SearchParameters extends SortParameters {
  q: string;
  langs: string[];
  page_size: string;
  page?: string;
  index_id?: string;
  facets?: string[];
  params?: string[];
  charts?: string[];
}
export interface SearchaliciousSearchInterface
  extends EventRegistrationInterface,
    SearchaliciousHistoryInterface {
  query: string;
  name: string;
  baseUrl: string;
  langs: string;
  index: string;
  pageSize: number;
  lastQuery?: string;
  lastFacetsFilters?: string;
  isQueryChanged: boolean;
  isFacetsChanged: boolean;
  isSearchChanged: boolean;
  canReset: boolean;

  updateSearchSignals(): void;
  search(): Promise<void>;
  _facetsNodes(): SearchaliciousFacets[];
  _facetsFilters(): string;
  resetFacets(launchSearch?: boolean): void;
  selectTermByTaxonomy(taxonomy: string, term: string): void;
}

// We should not use GET if other params than those are present in the search request
const supportedGETParams = new Set([
  'q',
  'langs',
  'page_size',
  'page',
  'fields',
  'sort_by',
  'facets',
  'index_id',
]);

// name of search params as an array (to ease iteration)

export const SearchaliciousSearchMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  /**
   * The search mixin, encapsulate the logic of dialog with server
   */
  class SearchaliciousSearchMixinClass extends SignalWatcher(
    SearchaliciousHistoryMixin(EventRegistrationMixin(superClass))
  ) {
    /**
     * Query that will be sent to searchalicious
     */
    @property({attribute: false})
    override query = '';

    /**
     * The name of this search
     */
    @property()
    override name = DEFAULT_SEARCH_NAME;

    /**
     * The base api url
     */
    @property({attribute: 'base-url'})
    baseUrl = '/';

    /**
     * Separated list of languages
     */
    @property()
    langs = 'en';

    /**
     * index to query
     */
    @property()
    index?: string;

    /**
     * Number of result per page
     */
    @property({type: Number, attribute: 'page-size'})
    pageSize = 10;

    /**
     * Number of result per page
     */
    @state()
    override _currentPage?: number;

    /**
     * Last search page count
     */
    @state()
    _pageCount?: number;

    /**
     * Last search results for current page
     */
    @state()
    _results?: {}[];

    /**
     * Last search total number of results
     */
    @state()
    _count?: number;

    /**
     * Last search query
     */
    lastQuery = '';
    /**
     * Last search facets filters
     */
    lastFacetsFilters = '';

    /**
     * Check if the query has changed since the last search
     */
    get isQueryChanged() {
      return this.query !== this.lastQuery;
    }

    /**
     * Check if the facets filters have changed since the last search
     */
    get isFacetsChanged() {
      return this._facetsFilters() !== this.lastFacetsFilters;
    }

    /**
     * Check if the search button text should be displayed
     */
    get isSearchChanged() {
      return this.isQueryChanged || this.isFacetsChanged;
    }

    /**
     * Check if the filters can be reset
     * Filters is facets filters and query
     */
    get canReset() {
      const isQueryChanged = this.query || this.isQueryChanged;
      const facetsChanged = this._facetsFilters() || this.isFacetsChanged;
      return Boolean(isQueryChanged || facetsChanged);
    }

    updateSearchSignals() {
      canResetSearch(this.name).value = this.canReset;
      isSearchChanged(this.name).value = this.isSearchChanged;
    }

    /** list of facets containers */
    _facetsParentNode() {
      return document.querySelectorAll(
        `searchalicious-facets[search-name=${this.name}]`
      );
    }

    /**
     * Return the list of searchalicious-chart nodes
     */
    _chartsNodes(): SearchaliciousChart[] {
      return Array.from(
        document.querySelectorAll(
          `searchalicious-chart[search-name=${this.name}`
        )
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
    }

    /**
     * @returns the sort element linked to this search ctl
     */
    override _sortElement = (): SearchaliciousSort | null => {
      let sortElement: SearchaliciousSort | null = null;
      document.querySelectorAll(`searchalicious-sort`).forEach((item) => {
        const sortElementItem = item as SearchaliciousSort;
        if (sortElementItem.searchName == this.name) {
          if (sortElement !== null) {
            console.warn(
              `searchalicious-sort element with search-name ${this.name} already exists, ignoring`
            );
          } else {
            sortElement = sortElementItem;
          }
        }
      });

      return sortElement;
    };

    /**
     * Wether search should be launched at page load
     */
    @property({attribute: 'auto-launch', type: Boolean})
    autoLaunch = false;

    /**
     * Launch search at page loaded if needed (we have a search in url)
     */
    firstSearch = () => {
      // we need to wait for the facets to be ready
      setTimeout(() => {
        const {launchSearch, values} = this.setParamFromUrl();
        if (this.autoLaunch || launchSearch) {
          // launch the first search event to trigger the search only once
          this.dispatchEvent(
            new CustomEvent(SearchaliciousEvents.LAUNCH_FIRST_SEARCH, {
              bubbles: true,
              composed: true,
              detail: {
                page: values[HistorySearchParams.PAGE],
              },
            })
          );
        }
      }, 0);
    };

    /**
     * @returns all searchalicious-facets elements linked to this search ctl
     */
    override _facetsNodes = (): SearchaliciousFacets[] => {
      const allNodes: SearchaliciousFacets[] = [];
      // search facets elements, we can't filter on search-name because of default value…
      this._facetsParentNode()?.forEach((item) => {
        const facetElement = item as SearchaliciousFacets;
        if (facetElement.searchName == this.name) {
          allNodes.push(facetElement);
        }
      });
      return allNodes;
    };

    /**
     * Get the list of facets we want to request
     */
    _facets(): string[] {
      const names = this._facetsNodes()
        .map((facets) => facets.getFacetsNames())
        .flat();
      return [...new Set(names)];
    }

    /**
     * Get the list of charts we want to request
     */
    _charts(): string[] {
      const names = this._chartsNodes().map((chart) => chart.getName());
      return [...new Set(names)];
    }

    /**
     * Get the filter linked to facets
     * @returns an expression to be added to query
     */
    override _facetsFilters = (): string => {
      const allFilters: string[] = this._facetsNodes()
        .map((facets) => facets.getSearchFilters())
        .flat();
      return allFilters.join(QueryOperator.AND);
    };

    resetFacets(launchSearch = true) {
      this._facetsNodes().forEach((facets) => facets.reset(launchSearch));
    }

    /*
     * Compute search URL, associated parameters and history entry
     * based upon the requested page, and the state of other search components
     * (search bar, facets, etc.)
     */
    _searchUrl(page?: number) {
      // remove trailing slash
      const baseUrl = this.baseUrl.replace(/\/+$/, '');
      const params = this.buildParams(page);
      // we needs a POST if a parameter is not supported by GET
      const needsPOST =
        Object.keys(params).filter((key) => !supportedGETParams.has(key))
          .length > 0;
      const history = this.buildHistoryParams(params);
      // remove empty values from params
      // (do this after buildHistoryParams to be sure to have all parameters)
      Object.entries(params).forEach(([key, value]) => {
        if (isNullOrUndefined(value)) {
          delete params[key as keyof SearchParameters];
        }
      });
      return {
        searchUrl: `${baseUrl}/search`,
        method: needsPOST ? 'POST' : 'GET',
        params,
        // this will help update browser history
        history,
      };
    }

    _paramsToQueryStr(params: SearchParameters): string {
      return Object.entries(params)
        .map(([key, value]) => {
          if (value.constructor === Array) {
            value = value.join(API_LIST_DIVIDER);
          }
          return `${encodeURIComponent(key)}=${encodeURIComponent(value!)}`;
        })
        .sort() // for perdictability in tests !
        .join('&');
    }

    // connect to our specific events
    override connectedCallback() {
      super.connectedCallback();
      this.addEventHandler(
        SearchaliciousEvents.LAUNCH_SEARCH,
        (event: Event) => {
          this._handleSearch(event);
        }
      );
      this.addEventHandler(SearchaliciousEvents.CHANGE_PAGE, (event) =>
        this._handleChangePage(event)
      );
      this.addEventHandler(SearchaliciousEvents.LAUNCH_FIRST_SEARCH, (event) =>
        this.search((event as CustomEvent)?.detail[HistorySearchParams.PAGE])
      );
      this.addEventHandler(
        SearchaliciousEvents.FACET_SELECTED,
        (event: Event) => {
          if (isTheSameSearchName(this.name, event)) {
            this.updateSearchSignals();
          }
        }
      );
    }
    // connect to our specific events
    override disconnectedCallback() {
      super.disconnectedCallback();
      this.removeEventHandler(
        SearchaliciousEvents.LAUNCH_SEARCH,
        (event: Event) => this._handleSearch(event)
      );
      this.removeEventHandler(SearchaliciousEvents.CHANGE_PAGE, (event) =>
        this._handleChangePage(event)
      );
      this.removeEventHandler(
        SearchaliciousEvents.LAUNCH_FIRST_SEARCH,
        (event) =>
          this.search((event as CustomEvent)?.detail[HistorySearchParams.PAGE])
      );
      this.removeEventHandler(SearchaliciousEvents.FACET_SELECTED, () => {
        this.updateSearchSignals();
      });
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    override firstUpdated(changedProperties: Map<any, any>) {
      super.firstUpdated(changedProperties);
      this.firstSearch();
    }

    /**
     * External component (like the search button)
     * can use the `searchalicious-search` event
     * to trigger a search.
     * It must have the search name in it's data.
     */
    _handleSearch(event: Event) {
      if (isTheSameSearchName(this.name, event)) {
        this.search();
      }
    }

    /**
     * External component (like the search pages)
     * can use the `searchalicious-change-page` event
     * to ask for page change
     * It must have the search name in it's data.
     */
    _handleChangePage(event: Event) {
      const detail = (event as ChangePageEvent).detail;
      if (isTheSameSearchName(this.name, event)) {
        this.search(detail.page);
      }
    }

    /**
     * Build the params to send to the search API
     * @param page
     */
    buildParams = (page?: number): SearchParameters => {
      const queryParts = [];
      this.lastQuery = this.query;
      if (this.query) {
        queryParts.push(this.query);
      }
      const facetsFilters = this._facetsFilters();
      this.lastFacetsFilters = this._facetsFilters();

      if (facetsFilters) {
        queryParts.push(facetsFilters);
      }
      const params: SearchParameters = {
        q: queryParts.join(' '),
        langs: this.langs
          .split(PROPERTY_LIST_DIVIDER)
          .map((lang) => lang.trim()),
        page_size: this.pageSize?.toString(),
        index_id: this.index,
      };
      // sorting parameters
      const sortElement = this._sortElement();
      if (sortElement) {
        Object.assign(params, sortElement.getSortParameters());
      }
      // page
      if (page) {
        params.page = page.toString();
      }
      // facets
      if (this._facets().length > 0) {
        params.facets = this._facets();
      }
      if (this._charts().length > 0) {
        params.charts = this._charts();
      }
      return params;
    };

    /**
     * Launching search
     */
    async search(page = 1) {
      // use to get the time of the search
      const {searchUrl, method, params, history} = this._searchUrl(page);
      setCurrentURLHistory(history);

      isSearchLoading(this.name).value = true;

      let response;
      if (method === 'GET') {
        response = await fetch(
          `${searchUrl}?${this._paramsToQueryStr(params)}`
        );
      } else {
        response = await fetch(searchUrl, {
          method: 'POST',
          body: JSON.stringify(params),
          headers: {
            'Content-Type': 'application/json',
          },
        });
      }
      // FIXME data should be typed…
      const data = await response.json();
      this._results = data.hits;
      this._count = data.count;
      this.pageSize = data.page_size;
      this._currentPage = data.page;
      this._pageCount = data.page_count;

      isSearchLoading(this.name).value = false;
      this.updateSearchSignals();

      searchResultDetail(this.name).value = {
        charts: data.charts,
        count: data.count,
        currentPage: this._currentPage!,
        displayTime: data.took,
        facets: data.facets,
        isCountExact: data.is_count_exact,
        isSearchLaunch: true,
        pageCount: this._pageCount!,
        pageSize: this.pageSize,
        results: this._results!,
      };

      this.updateSearchSignals();
    }
  }

  return SearchaliciousSearchMixinClass as Constructor<SearchaliciousSearchInterface> &
    T;
};
