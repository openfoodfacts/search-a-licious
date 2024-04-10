import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Constructor<T = {}> = new (...args: any[]) => T;

export declare class SearchaliciousSearchInterface {
  query: string;
  name: string;
  baseUrl: string;
  langs: string;
  pageSize: Number;

  search(): Promise<void>;
}

export const SearchaliciousSearchMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  /**
   * The search mixin, encapsulate the logic of dialog with server
   */
  class SearchaliciousSearchMixinClass extends superClass {
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
    @property({attribute: 'batse-url'})
    baseUrl = '/';

    /**
     * Separated list of languages
     */
    @property()
    langs = 'en';

    // TODO: should be on results element instead
    @property({type: Number, attribute: 'page-size'})
    pageSize: Number = 10;

    @state()
    pageCount?: Number;

    @state()
    results?: {}[];

    @state()
    count?: Number;

    // TODO: this should be on results element instead
    _searchUrl() {
      // remove trailing slash
      const baseUrl = this.baseUrl.replace(/\/+$/, '');
      // build parameters
      const params = {
        q: this.query,
        langs: this.langs,
        page_size: this.pageSize.toString(),
      };
      const queryStr = Object.entries(params)
        .map(
          ([key, value]) =>
            `${encodeURIComponent(key)}=${encodeURIComponent(value)}`
        )
        .join('&');
      // FIXME: handle page
      return `${baseUrl}/search?${queryStr}`;
    }

    /**
     * Launching search
     */
    async search() {
      const response = await fetch(this._searchUrl());
      const data = await response.json();
      this.results = data.hits;
      this.count = data.count;
      this.pageCount = data.page_count;
      // dispatch an event with the results
      this.dispatchEvent(new CustomEvent(`searchalicious-result`, {}));
    }
  }

  return SearchaliciousSearchMixinClass as Constructor<SearchaliciousSearchInterface> &
    T;
};

declare global {
  interface GlobalEventHandlersEventMap {
    'searchalicious-result': CustomEvent<{}>;
  }
}
