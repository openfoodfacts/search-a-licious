import {LitElement, ReactiveElement} from 'lit';
import {property} from 'lit/decorators.js';

import {Constructor} from './utils';
import {DEFAULT_SEARCH_NAME} from '../utils/constants';
import {SearchResultDetail, searchResultDetail} from '../signals';
import {Signal, SignalWatcher} from '@lit-labs/preact-signals';
import {EventRegistrationInterface} from '../interfaces/events-interfaces';
import {EventRegistrationMixin} from '../event-listener-setup';

export interface SearchaliciousResultsCtlInterface
  extends EventRegistrationInterface {
  searchName: string;
  searchResultDetailSignal: Signal<SearchResultDetail>;
  searchResultDetail: SearchResultDetail;
}

/**
 * Common Mixin for elements that react upon a search result
 * It can be to display results, facets or pagination.
 */
export const SearchaliciousResultCtlMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  /**
   * The search mixin, encapsulate the logic of dialog with server
   */
  class SearchaliciousResultCtlMixinClass extends SignalWatcher(
    EventRegistrationMixin(superClass)
  ) {
    /**
     * the search we display result for,
     * this corresponds to `name` attribute of corresponding search-bar
     */
    @property({attribute: 'search-name'})
    searchName = DEFAULT_SEARCH_NAME;

    get searchResultDetailSignal() {
      return searchResultDetail(this.searchName);
    }

    get searchResultDetail() {
      return this.searchResultDetailSignal.value;
    }
  }

  return SearchaliciousResultCtlMixinClass as Constructor<
    SearchaliciousResultsCtlInterface & ReactiveElement
  > &
    T;
};
