import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';

import {
  EventRegistrationInterface,
  EventRegistrationMixin,
} from '../event-listener-setup';
import {SearchaliciousEvents} from '../utils/enums';
import {SearchResultEvent} from '../events';
import {Constructor} from './utils';

export interface SearchaliciousResultsCtlInterface
  extends EventRegistrationInterface {
  searchName: string;
  searchLaunched: Boolean;

  // sub class must override this one to display results
  handleResults(event: SearchResultEvent): void;
  // this is the registered handler
  _handleResults(event: Event): void;
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
  class SearchaliciousResultCtlMixinClass extends EventRegistrationMixin(
    superClass
  ) {
    /**
     * the search we display result for,
     * this corresponds to `name` attribute of corresponding search-bar
     */
    @property({attribute: 'search-name'})
    searchName = 'searchalicious';

    /**
     * this will be true if we already launched a search
     */
    @state()
    searchLaunched = false;

    handleResults(_: SearchResultEvent) {
      throw Error(
        'You must provide a handleResults function in you implementation'
      );
    }

    /**
     * event handler for NEW_RESULT events
     */
    _handleResults(event: Event) {
      // check if event is for our search
      const resultEvent = event as SearchResultEvent;
      const detail = resultEvent.detail;
      if (detail.searchName === this.searchName) {
        this.searchLaunched = true;
        // call the real method
        this.handleResults(resultEvent);
      }
    }

    /**
     * Connect search event handlers.
     */
    override connectedCallback() {
      super.connectedCallback();
      this.addEventHandler(SearchaliciousEvents.NEW_RESULT, (event) =>
        this._handleResults(event)
      );
    }
    // connect to our specific events
    override disconnectedCallback() {
      super.disconnectedCallback();
      this.removeEventHandler(SearchaliciousEvents.NEW_RESULT, (event) =>
        this._handleResults(event)
      );
    }
  }

  return SearchaliciousResultCtlMixinClass as Constructor<SearchaliciousResultsCtlInterface> &
    T;
};
