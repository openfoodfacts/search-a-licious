import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';
import {EventRegistrationMixin} from './event-listener-setup';
import {SearchaliciousEvents} from './enums';
import {SearchResultEvent, SearchResultDetail} from './events';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Constructor<T = {}> = new (...args: any[]) => T;

export declare class SearchaliciousSearchInterface {
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

    // TODO: should be on results element instead
    @property({type: Number, attribute: 'page-size'})
    pageSize = 10;

    @state()
    _pageCount?: number;

    @state()
    _results?: {}[];

    @state()
    _count?: number;

    // TODO: this should be on results element instead
    _searchUrl() {
      // remove trailing slash
      const baseUrl = this.baseUrl.replace(/\/+$/, '');
      // build parameters
      const params = {
        q: this.query,
        langs: this.langs,
        page_size: this.pageSize.toString(),
        index: this.index,
      };
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
      // FIXME: handle pagination
      return `${baseUrl}/search?${queryStr}`;
    }

    // connect to our specific events
    override connectedCallback() {
      super.connectedCallback();
      this.addEventHandler(SearchaliciousEvents.LAUNCH_SEARCH, (event: Event) =>
        this._handleSearch(event)
      );
    }
    // connect to our specific events
    override disconnectedCallback() {
      super.disconnectedCallback();
      this.removeEventHandler(
        SearchaliciousEvents.LAUNCH_SEARCH,
        (event: Event) => this._handleSearch(event)
      );
    }

    /**
     * External component (like the search button)
     * can use the `searchalicious-search` event
     * to trigger a search.
     * It must have the search name in it's data.
     */
    _handleSearch(event: Event) {
      const detail = (event as CustomEvent).detail;
      if (detail.search_name === this.name) {
        this.search();
      }
    }

    /**
     * Launching search
     */
    async search() {
      const response = await fetch(this._searchUrl());
      const data = await response.json();
      this._results = data.hits;
      this._count = data.count;
      this._pageCount = data.page_count;
      const detail: SearchResultDetail = {
        searchName: this.name,
        results: this._results!,
        count: this._count!,
        pageCount: this._pageCount!,
      };
      // dispatch an event with the results
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
