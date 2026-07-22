import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';
import {SignalWatcher} from '@lit-labs/preact-signals';
import {DEFAULT_SEARCH_NAME} from '../utils/constants';
import {Constructor} from './utils';
import {canResetSearch, isSearchChanged} from '../signals';
import {SearchaliciousHistoryInterface} from '../interfaces/history-interfaces';

export declare class SearchaliciousStateInterface {
  baseUrl: string;
  langs: string;
  index?: string;
  boostPhrase: boolean;
  pageSize: number;
  _pageCount?: number;
  _results?: {}[];
  _count?: number;
  lastQuery: string;
  lastFacetsFilters: string;
  autoLaunch: boolean;

  get isQueryChanged(): boolean;
  get isFacetsChanged(): boolean;
  get isSearchChanged(): boolean;
  get canReset(): boolean;

  updateSearchSignals(): void;
}

export const SearchaliciousStateMixin = <T extends Constructor<LitElement & SearchaliciousHistoryInterface>>(
  superClass: T
) => {
  class SearchaliciousStateMixinClass extends SignalWatcher(superClass) {
    @property({attribute: false})
    override query = '';

    @property()
    override name = DEFAULT_SEARCH_NAME;

    @property({attribute: 'base-url'})
    baseUrl = '/';

    @property()
    langs = 'en';

    @property()
    index?: string;

    @property({type: Boolean, attribute: 'boost-phrase'})
    boostPhrase = false;

    @property({type: Number, attribute: 'page-size'})
    pageSize = 10;

    @state()
    override _currentPage?: number;

    @state()
    _pageCount?: number;

    @state()
    _results?: {}[];

    @state()
    _count?: number;

    lastQuery = '';
    lastFacetsFilters = '';

    @property({attribute: 'auto-launch', type: Boolean})
    autoLaunch = false;

    get isQueryChanged() {
      return this.query !== this.lastQuery;
    }

    get isFacetsChanged() {
      return this._facetsFilters() !== this.lastFacetsFilters;
    }

    get isSearchChanged() {
      return this.isQueryChanged || this.isFacetsChanged;
    }

    get canReset() {
      const isQueryChanged = this.query || this.isQueryChanged;
      const facetsChanged = this._facetsFilters() || this.isFacetsChanged;
      return Boolean(isQueryChanged || facetsChanged);
    }

    updateSearchSignals() {
      canResetSearch(this.name).value = this.canReset;
      isSearchChanged(this.name).value = this.isSearchChanged;
    }
  }

  return SearchaliciousStateMixinClass as unknown as Constructor<SearchaliciousStateInterface> & T;
};
