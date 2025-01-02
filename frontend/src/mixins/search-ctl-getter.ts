import {Constructor} from './utils';
import {
  SearchaliciousSearchInterface,
  SearchCtlGetInterface,
} from '../interfaces/search-ctl-interfaces';

/**
 * Some component may want to refer to the corresponding search controller instance
 *
 * This mixin provides a getter to get the corresponding search controller instance
 */
export const SearchCtlGetMixin = <T extends Constructor<Object>>(
  superClass: T
) => {
  class SearchCtlGetMixinClass extends superClass {
    get searchName(): string {
      throw Error('searchName attribute must be implemented in base class');
    }

    _searchCtl_cache: SearchaliciousSearchInterface | undefined;

    /** get corresponding search bar instance */
    getSearchCtl(): SearchaliciousSearchInterface {
      if (!this._searchCtl_cache) {
        let searchCtl: SearchaliciousSearchInterface | undefined = undefined;
        document.querySelectorAll(`searchalicious-bar`).forEach((item) => {
          const candidate = item as SearchaliciousSearchInterface;
          if (candidate.name === this.searchName) {
            searchCtl = candidate;
          }
        });
        if (searchCtl == null) {
          throw new Error(`No search bar found for ${this.searchName}`);
        }
        // optimize
        this._searchCtl_cache = searchCtl;
      }
      return this._searchCtl_cache;
    }
  }

  return SearchCtlGetMixinClass as Constructor<SearchCtlGetInterface> & T;
};
