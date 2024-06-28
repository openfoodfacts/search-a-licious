import {LitElement} from 'lit';
import {Constructor} from './utils';
import {BaseSearchDetail, LaunchSearchEvent} from '../events';
import {SearchaliciousEvents, SearchNameProperty} from '../utils/enums';
import {property} from 'lit/decorators.js';

export interface SearchActionMixinInterface {
  searchName: SearchNameProperty;
  _launchSearch(): Promise<void>;
}

/**
 * A mixin class for search actions.
 * It extends the LitElement class and adds search functionality.
 * It is used to launch a search event.
 * @param {Constructor<LitElement>} superClass - The superclass to extend from.
 * @returns {Constructor<SearchActionMixinInterface> & T} - The extended class with search functionality.
 */
export const SearchActionMixin = <T extends Constructor<LitElement>>(
  superClass: T
): Constructor<SearchActionMixinInterface> & T => {
  class SearchActionMixinClass extends superClass {
    @property({attribute: 'search-name'})
    searchName: SearchNameProperty = SearchNameProperty.SEARCHALICIOUS;

    /**
     * Launches a search event.
     * It creates a new event with the search name and dispatches it.
     */
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
