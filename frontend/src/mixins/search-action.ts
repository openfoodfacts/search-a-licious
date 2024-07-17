import {LitElement} from 'lit';
import {Constructor} from './utils';
import {BaseSearchDetail, LaunchSearchEvent} from '../events';
import {SearchaliciousEvents} from '../utils/enums';
import {property} from 'lit/decorators.js';
import {DEFAULT_SEARCH_NAME} from '../utils/constants';

export interface SearchActionMixinInterface {
  searchName: string;
  _launchSearch(): Promise<void>;
}

/**
 * A mixin class for search actions.
 * It extends the LitElement class and adds search functionality.
 * It is used to launch a search event.
 * @param {Constructor<LitElement>} superClass - The superclass to extend from.
 * @event searchalicious-search - Fired according to component needs.
 * @returns {Constructor<SearchActionMixinInterface> & T} - The extended class with search functionality.
 */
export const SearchActionMixin = <T extends Constructor<LitElement>>(
  superClass: T
): Constructor<SearchActionMixinInterface> & T => {
  class SearchActionMixinClass extends superClass {
    /**
     * The name of the search bar this sort applies to.
     *
     * It must correspond to the `name` property of the corresponding `search-bar` component.
     *
     * It enable having multiple search bars on the same page.
     *
     * It defaults to `searchalicious`
     */
    @property({attribute: 'search-name'})
    searchName = DEFAULT_SEARCH_NAME;

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
