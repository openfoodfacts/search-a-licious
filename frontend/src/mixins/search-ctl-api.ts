import {LitElement} from 'lit';
import {Constructor} from './utils';
import {isNullOrUndefined} from '../utils';
import {API_LIST_DIVIDER, PROPERTY_LIST_DIVIDER} from '../utils/constants';
import {SearchParameters} from '../interfaces/search-params-interfaces';
import {setCurrentURLHistory} from '../utils/url';
import {isSearchLoading, searchResultDetail} from '../signals';
import {SearchaliciousStateInterface} from './search-ctl-state';
import {SearchaliciousDomInterface} from './search-ctl-dom';
import {SearchaliciousHistoryInterface} from '../interfaces/history-interfaces';

export declare class SearchaliciousApiInterface {
  _searchUrl(page?: number): any;
  _paramsToQueryStr(params: SearchParameters): string;
  buildParams(page?: number): {params: SearchParameters; needsPOST: boolean};
  search(page?: number): Promise<void>;
}

export const SearchaliciousApiMixin = <T extends Constructor<LitElement & SearchaliciousStateInterface & SearchaliciousDomInterface & SearchaliciousHistoryInterface>>(
  superClass: T
) => {
  class SearchaliciousApiMixinClass extends superClass {
    _searchUrl(page?: number) {
      const baseUrl = this.baseUrl.replace(/\/+$/, '');
      const {params, needsPOST} = this.buildParams(page);
      const history = this.buildHistoryParams(params);
      Object.entries(params).forEach(([key, value]) => {
        if (isNullOrUndefined(value)) {
          delete params[key as keyof SearchParameters];
        }
      });
      return {
        searchUrl: `${baseUrl}/search`,
        method: needsPOST ? 'POST' : 'GET',
        params,
        history,
      };
    }

    _paramsToQueryStr(params: SearchParameters): string {
      return Object.entries(params)
        .map(([key, value]) => {
          if (value === false) {
            return null;
          }
          if (value.constructor === Array) {
            value = value.join(API_LIST_DIVIDER);
          }
          return `${encodeURIComponent(key)}=${encodeURIComponent(value as string)}`;
        })
        .filter((val) => val !== null)
        .sort()
        .join('&');
    }

    buildParams = (page?: number) => {
      let needsPOST = false;
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
        boost_phrase: this.boostPhrase,
        langs: this.langs
          .split(PROPERTY_LIST_DIVIDER)
          .map((lang) => lang.trim()),
        page_size: this.pageSize?.toString(),
        index_id: this.index,
      };
      
      const sortElement = this._sortElement();
      if (sortElement) {
        const sortParameters = sortElement.getSortParameters();
        if (sortParameters) {
          needsPOST = true;
          Object.assign(params, sortParameters);
        }
      }
      
      if (page) {
        params.page = page.toString();
      }
      
      if (this._facetsNames().length > 0) {
        params.facets = this._facetsNames();
      }

      const charts = this._chartParams(!needsPOST);
      if (charts) {
        params.charts = charts;
      }
      return {params, needsPOST};
    };

    async search(page = 1) {
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
      
      // FIXME data should be typed
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

  return SearchaliciousApiMixinClass as unknown as Constructor<SearchaliciousApiInterface> & T;
};
