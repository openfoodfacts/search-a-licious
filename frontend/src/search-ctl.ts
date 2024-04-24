import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';
import {
  EventRegistrationInterface,
  EventRegistrationMixin,
} from './event-listener-setup';
import {SearchaliciousEvents} from './enums';
import {
  ChangePageEvent,
  LaunchSearchEvent,
  SearchResultEvent,
  SearchResultDetail,
} from './events';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Constructor<T = {}> = new (...args: any[]) => T;

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

    // TODO: this should be on results element instead
    _searchUrl(page?: number) {
      // remove trailing slash
      const baseUrl = this.baseUrl.replace(/\/+$/, '');
      // build parameters
      const params: {
        q: string;
        langs: string;
        page_size: string;
        page?: string;
        index?: string;
      } = {
        q: this.query,
        langs: this.langs,
        page_size: this.pageSize.toString(),
        index: this.index,
      };
      if (page) {
        params.page = page.toString();
      }
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
      return `${baseUrl}/search?${queryStr}`;
    }

    // connect to our specific events
    override connectedCallback() {
      super.connectedCallback();
      this.addEventHandler(SearchaliciousEvents.LAUNCH_SEARCH, (event: Event) =>
        this._handleSearch(event)
      );
      this.addEventHandler(SearchaliciousEvents.CHANGE_PAGE, (event) =>
        this._handleChangePage(event)
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
     * Launching search
     */
    async search(page?: number) {
      const response = await fetch(this._searchUrl(page));
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
        aggregations: data.aggregations,
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
