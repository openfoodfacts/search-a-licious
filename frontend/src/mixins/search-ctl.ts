import {LitElement} from 'lit';
import {EventRegistrationMixin} from '../event-listener-setup';
import {SearchaliciousEvents} from '../utils/enums';
import {ChangePageEvent} from '../events';
import {Constructor} from './utils';
import {SearchaliciousSearchInterface} from '../interfaces/search-ctl-interfaces';
import {HistorySearchParams} from '../interfaces/history-interfaces';
import {SearchaliciousHistoryMixin} from './history';
import {isTheSameSearchName} from '../utils/search';

import {SearchaliciousStateMixin} from './search-ctl-state';
import {SearchaliciousDomMixin} from './search-ctl-dom';
import {SearchaliciousApiMixin} from './search-ctl-api';

export const SearchaliciousSearchMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  class SearchaliciousSearchMixinClass extends SearchaliciousApiMixin(
    SearchaliciousDomMixin(
      SearchaliciousStateMixin(
        SearchaliciousHistoryMixin(EventRegistrationMixin(superClass))
      )
    )
  ) {
    firstSearch = () => {
      // we need to wait for the facets to be ready
      setTimeout(() => {
        const {launchSearch, values} = this.setParamFromUrl();
        if (this.autoLaunch || launchSearch) {
          this.dispatchEvent(
            new CustomEvent(SearchaliciousEvents.LAUNCH_FIRST_SEARCH, {
              bubbles: true,
              composed: true,
              detail: {
                page: values[HistorySearchParams.PAGE],
              },
            })
          );
        }
      }, 0);
    };

    override connectedCallback() {
      super.connectedCallback();
      this.addEventHandler(
        SearchaliciousEvents.LAUNCH_SEARCH,
        (event: Event) => {
          this._handleSearch(event);
        }
      );
      this.addEventHandler(SearchaliciousEvents.CHANGE_PAGE, (event) =>
        this._handleChangePage(event)
      );
      this.addEventHandler(SearchaliciousEvents.LAUNCH_FIRST_SEARCH, (event) =>
        this.search((event as CustomEvent)?.detail[HistorySearchParams.PAGE])
      );
      this.addEventHandler(
        SearchaliciousEvents.FACET_SELECTED,
        (event: Event) => {
          if (isTheSameSearchName(this.name, event)) {
            this.updateSearchSignals();
          }
        }
      );
    }

    override disconnectedCallback() {
      super.disconnectedCallback();
      this.removeEventHandler(
        SearchaliciousEvents.LAUNCH_SEARCH,
        (event: Event) => this._handleSearch(event)
      );
      this.removeEventHandler(SearchaliciousEvents.CHANGE_PAGE, (event) =>
        this._handleChangePage(event)
      );
      this.removeEventHandler(
        SearchaliciousEvents.LAUNCH_FIRST_SEARCH,
        (event) =>
          this.search((event as CustomEvent)?.detail[HistorySearchParams.PAGE])
      );
      this.removeEventHandler(SearchaliciousEvents.FACET_SELECTED, () => {
        this.updateSearchSignals();
      });
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    override firstUpdated(changedProperties: Map<any, any>) {
      super.firstUpdated(changedProperties);
      this.firstSearch();
    }

    _handleSearch(event: Event) {
      if (isTheSameSearchName(this.name, event)) {
        this.search();
      }
    }

    _handleChangePage(event: Event) {
      const detail = (event as ChangePageEvent).detail;
      if (isTheSameSearchName(this.name, event)) {
        this.search(detail.page);
      }
    }
  }

  return SearchaliciousSearchMixinClass as unknown as Constructor<SearchaliciousSearchInterface> & T;
};
