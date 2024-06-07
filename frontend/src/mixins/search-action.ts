import {LitElement} from 'lit';
import {Constructor} from './utils';
import {BaseSearchDetail, LaunchSearchEvent} from '../events';
import {SearchaliciousEvents} from '../enums';
import {property} from 'lit/decorators.js';

export interface SearchActionMixinInterface {
  searchName: string;
  _launchSearch(): Promise<void>;
}

export const SearchActionMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  class SearchActionMixinClass extends superClass {
    @property({attribute: 'search-name'})
    searchName = 'searchalicious';

    _launchSearch() {
      const detail: BaseSearchDetail = {searchName: this.searchName};
      // fire the search event
      const event = new CustomEvent(SearchaliciousEvents.LAUNCH_SEARCH, {
        bubbles: true,
        composed: true,
        detail: detail,
      }) as LaunchSearchEvent;
      this.dispatchEvent(event);
    }
  }

  return SearchActionMixinClass as Constructor<SearchActionMixinInterface> & T;
};
