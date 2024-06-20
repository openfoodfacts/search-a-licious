import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';
import {
  EventRegistrationInterface,
  EventRegistrationMixin,
} from '../event-listener-setup';
import {QueryOperator, SearchaliciousEvents} from '../utils/enums';
import {
  ChangePageEvent,
  LaunchSearchEvent,
  SearchResultEvent,
  SearchResultDetail,
} from '../events';
import {Constructor} from './utils';
import {SearchaliciousSort} from '../search-sort';
import {SearchaliciousFacets} from '../search-facets';
import {setCurrentURLHistory} from '../utils/url';
import {FACETS_DIVIDER} from '../utils/constants';
import {
  HistorySearchParams,
  SearchaliciousHistoryInterface,
  SearchaliciousHistoryMixin,
} from './history';

export type BuildParamsOutput = {
  q: string;
  langs: string;
  page_size: string;
  page?: string;
  index?: string;
  facets?: string;
};
export interface SearchaliciousSearchInterface
  extends EventRegistrationInterface,
    SearchaliciousHistoryInterface {
  query: string;
  name: string;
  baseUrl: string;
  langs: string;
  index: string;
  pageSize: number;

  search(): Promise<void>;
  _facetsNodes(): SearchaliciousFacets[];
  _facetsFilters(): string;
}

// name of search params as an array (to ease iteration)

export const SearchaliciousSearchMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  /**
   * The search mixin, encapsulate the logic of dialog with server
   */
  class SearchaliciousSearchMixinClass extends SearchaliciousHistoryMixin(
    EventRegistrationMixin(superClass)
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
    override name = 'searchalicious';

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
      const facetsElements = document.querySelectorAll('searchalicious-facets');
      facetsElements.forEach((item) => {
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
     * Get the filter linked to facets
     * @returns an expression to be added to query
     */
    override _facetsFilters = (): string => {
      const allFilters: string[] = this._facetsNodes()
        .map((facets) => facets.getSearchFilters())
        .flat();
      return allFilters.join(QueryOperator.AND);
    };
    /*
     * Compute search URL, associated parameters and history entry
     * based upon the requested page, and the state of other search components
     * (search bar, facets, etc.)
     */
    _searchUrl(page?: number) {
      // remove trailing slash
      const baseUrl = this.baseUrl.replace(/\/+$/, '');
      const params = this.buildParams(page);
      const queryStr = Object.entries(params)
        .filter(
          ([_, value]) => value != null // null or undefined
        )
        .map(
          ([key, value]) =>
            `${encodeURIComponent(key)}=${encodeURIComponent(value!)}`
        )
        .sort() // for perdictability in tests !
        .join('&');
      return {
        searchUrl: `${baseUrl}/search?${queryStr}`,
        q: queryStr,
        params,
        // this will help update browser history
        history: this.buildHistoryParams(params),
      };
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
      const detail = (event as LaunchSearchEvent).detail;
      if (detail.searchName === this.name) {
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
      if (detail.searchName === this.name) {
        this.search(detail.page);
      }
    }

    /**
     * Build the params to send to the search API
     * @param page
     */
    buildParams = (page?: number): BuildParamsOutput => {
      const queryParts = [];
      if (this.query) {
        queryParts.push(this.query);
      }
      const facetsFilters = this._facetsFilters();
      if (facetsFilters) {
        queryParts.push(facetsFilters);
      }
      const params: {
        q: string;
        langs: string;
        page_size: string;
        page?: string;
        index?: string;
        facets?: string;
      } = {
        q: queryParts.join(' '),
        langs: this.langs,
        page_size: this.pageSize.toString(),
        index: this.index,
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
        params.facets = this._facets().join(FACETS_DIVIDER);
      }
      return params;
    };

    /**
     * Launching search
     */
    async search(page?: number) {
      const {searchUrl, history} = this._searchUrl(page);
      setCurrentURLHistory(history);
      const response = await fetch(searchUrl);
      // FIXME data should be typed…
      const data = await response.json();
      this._results = data.hits;
      this._count = data.count;
      this.pageSize = data.page_size;
      this._currentPage = data.page;
      this._pageCount = data.page_count;
      // dispatch an event with the results
      const detail: SearchResultDetail = {
        searchName: this.name,
        results: this._results!,
        count: this._count!,
        pageCount: this._pageCount!,
        currentPage: this._currentPage!,
        pageSize: this.pageSize,
        facets: data.facets,
      };
      this.dispatchEvent(
        new CustomEvent(SearchaliciousEvents.NEW_RESULT, {
          bubbles: true,
          composed: true,
          detail: detail,
        })
      );
    }
  }

  return SearchaliciousSearchMixinClass as Constructor<SearchaliciousSearchInterface> &
    T;
};

declare global {
  interface GlobalEventHandlersEventMap {
    'searchalicious-result': SearchResultEvent;
  }
}
