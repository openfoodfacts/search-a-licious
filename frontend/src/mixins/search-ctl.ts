import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';
import {
  EventRegistrationInterface,
  EventRegistrationMixin,
} from '../event-listener-setup';
import {SearchaliciousEvents} from '../utils/enums';
import {
  ChangePageEvent,
  LaunchSearchEvent,
  SearchResultEvent,
  SearchResultDetail,
} from '../events';
import {Constructor} from './utils';
import {SearchaliciousFacets} from './search-facets';
import {
  addParamPrefixes,
  removeParamPrefixes,
  removeParenthesis,
  setCurrentURLHistory,
} from './utils/url';
import {FACETS_DIVIDER, OFF_PREFIX, QueryOperator} from './utils/constants';
import {isNullOrUndefined} from './utils';

export type BuildParamsOutput = {
  q: string;
  langs: string;
  page_size: string;
  page?: string;
  index?: string;
  facets?: string;
};
export interface SearchaliciousSearchInterface
  extends EventRegistrationInterface {
  query: string;
  name: string;
  baseUrl: string;
  langs: string;
  index: string;
  pageSize: number;

  search(): Promise<void>;
}
export enum HistorySearchParams {
  QUERY = 'q',
  FACETS_FILTERS = 'facetsFilters',
  PAGE = 'page',
}

export const SEARCH_PARAMS = Object.values(HistorySearchParams);

export type HistoryParams = {
  [key in HistorySearchParams]?: string;
};
export type HistoryOutput = {
  query?: string;
  page?: number;
  selectedTermsByFacet?: Record<string, string[]>;
};

/**
 * Object to convert the URL params to the original values
 */
const HISTORY_VALUES: Record<
  HistorySearchParams,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (history: Record<string, string>) => Record<string, any>
> = {
  [HistorySearchParams.PAGE]: (history) =>
    history.page
      ? {
          page: parseInt(history.page),
        }
      : {},
  [HistorySearchParams.QUERY]: (history) => {
    // Avoid empty query but allow empty string
    if (isNullOrUndefined(history.q)) {
      return {};
    }
    return {
      query: history.q,
    };
  },
  [HistorySearchParams.FACETS_FILTERS]: (history) => {
    if (!history.facetsFilters) {
      return {};
    }
    const selectedTermsByFacet = history.facetsFilters
      .split(QueryOperator.AND)
      .reduce((acc, filter) => {
        const [key, value] = filter.split(':');
        acc[key] = removeParenthesis(value).split(QueryOperator.OR);
        return acc;
      }, {} as Record<string, string[]>);

    return {
      selectedTermsByFacet,
    };
  },
};

export const SearchaliciousSearchMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  /**
   * The search mixin, encapsulate the logic of dialog with server
   */
  class SearchaliciousSearchMixinClass extends EventRegistrationMixin(
    superClass
  ) {
    /**
     * Query that will be sent to searchalicious
     */
    @property({attribute: false})
    query = '';

    /**
     * The name of this search
     */
    @property()
    name = 'searchalicious';

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
    _currentPage?: number;

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
     * @returns all searchalicious-facets elements linked to this search ctl
     */
    _facetsNodes(): SearchaliciousFacets[] {
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
    }

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
    _facetsFilters(): string {
      const allFilters: string[] = this._facetsNodes()
        .map((facets) => facets.getSearchFilters())
        .flat();
      return allFilters.join(QueryOperator.AND);
    }
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
      this.addEventHandler(SearchaliciousEvents.LAUNCH_FIRST_SEARCH, () =>
        this.firstSearch()
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
      this.removeEventHandler(SearchaliciousEvents.LAUNCH_FIRST_SEARCH, () =>
        this.firstSearch()
      );
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
      if (page) {
        params.page = page.toString();
      }
      if (this._facets().length > 0) {
        params.facets = this._facets().join(FACETS_DIVIDER);
      }
      return params;
    };

    /**
     * Build the history params from the current state
     * It will be used to update the URL when searching
     * @param params
     */
    buildHistoryParams = (params: BuildParamsOutput) => {
      return addParamPrefixes(
        {
          [HistorySearchParams.QUERY]: this.query,
          [HistorySearchParams.FACETS_FILTERS]: this._facetsFilters(),
          [HistorySearchParams.PAGE]: params.page,
        },
        OFF_PREFIX
      ) as HistoryParams;
    };

    /**
     * Convert the URL params to the original values
     * @param params
     */
    paramsToOriginalValues = (params: URLSearchParams): HistoryOutput => {
      const values: HistoryOutput = {};
      const history = removeParamPrefixes(
        Object.fromEntries(params),
        OFF_PREFIX
      );
      for (const key of SEARCH_PARAMS) {
        Object.assign(values, HISTORY_VALUES[key](history));
      }
      return values;
    };

    /**
     * Set the values from the history
     * It will set the params from the URL params
     * @param values
     */
    setValuesFromHistory = (values: HistoryOutput) => {
      this.query = values.query ?? '';
      this._currentPage = values.page;
      this._facetsNodes().forEach((facets) => {
        facets._facetNodes().forEach((facet) => {
          if (values.selectedTermsByFacet?.[facet.name]?.length) {
            facet.setSelectedTerms(values.selectedTermsByFacet[facet.name]);
          }
        });
      });
    };

    firstSearch = () => {
      const params = new URLSearchParams(window.location.search);
      const values = this.paramsToOriginalValues(params);

      // Timeout to wait for all facets to be ready
      setTimeout(() => {
        this.setValuesFromHistory(values);
        if (Object.keys(values).length) {
          this.search();
        }
      }, 100);
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
