import {SearchaliciousFacetsInterface} from './facets-interfaces';
import {SearchaliciousSortInterface} from './sort-interfaces';
import {SearchParameters} from './search-params-interfaces';

/**
 * A set of values that can be deduced from parameters,
 * and are easy to use to set search components to corresponding values
 */
export type HistoryOutput = {
  query?: string;
  page?: number;
  sortOptionId?: string;
  selectedTermsByFacet?: Record<string, string[]>;
  history: HistoryParams;
};

// type of object containing search parameters
export type HistoryParams = {
  [key in HistorySearchParams]?: string;
};

/**
 * Parameters we need to put in URL to be able to deep link the search
 */
export enum HistorySearchParams {
  QUERY = 'q',
  FACETS_FILTERS = 'facetsFilters',
  PAGE = 'page',
  SORT_BY = 'sort_by',
}

export type SearchaliciousHistoryInterface = {
  query: string;
  name: string;
  _currentPage?: number;
  relatedFacets: () => SearchaliciousFacetsInterface[];
  _facetsFilters: () => string;
  _sortElement: () => SearchaliciousSortInterface | null;
  convertHistoryParamsToValues: (params: URLSearchParams) => HistoryOutput;
  setValuesFromHistory: (values: HistoryOutput) => void;
  buildHistoryParams: (params: SearchParameters) => HistoryParams;
  setParamFromUrl: () => {launchSearch: boolean; values: HistoryOutput};
};
