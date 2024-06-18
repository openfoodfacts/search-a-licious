import {LitElement} from 'lit';
import {
  addParamPrefixes,
  removeParamPrefixes,
  removeParenthesis,
} from '../utils/url';
import {isNullOrUndefined} from '../utils';
import {BuildParamsOutput} from './search-ctl';
import {property} from 'lit/decorators.js';
import {QueryOperator} from '../utils/enums';
import {SearchaliciousFacets} from '../search-facets';
import {Constructor} from './utils';

export type SearchaliciousHistoryInterface = {
  query: string;
  name: string;
  _currentPage?: number;
  _facetsNodes: () => SearchaliciousFacets[];
  _facetsFilters: () => string;
  convertHistoryParamsToValues: (params: URLSearchParams) => HistoryOutput;
  setValuesFromHistory: (values: HistoryOutput) => void;
  buildHistoryParams: (params: BuildParamsOutput) => HistoryParams;
  setParamFromUrl: () => {launchSearch: boolean; values: HistoryOutput};
};

export type HistoryOutput = {
  query?: string;
  page?: number;
  selectedTermsByFacet?: Record<string, string[]>;
};
/**
 * Parameters we need to put in URL to be able to deep link the search
 */
export enum HistorySearchParams {
  QUERY = 'q',
  FACETS_FILTERS = 'facetsFilters',
  PAGE = 'page',
}

// name of search params as an array (to ease iteration)
export const SEARCH_PARAMS = Object.values(HistorySearchParams);

// type of object containing search parameters
export type HistoryParams = {
  [key in HistorySearchParams]?: string;
};
/**
 * Object to convert the URL params to the original values
 *
 * It maps parameter names to a function to transforms it to a JS value
 */
const HISTORY_VALUES: Record<
  HistorySearchParams,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (history: Record<string, string>) => Record<string, any>
> = {
  [HistorySearchParams.PAGE]: (history) =>
    history.page
      ? {
          page: parseInt(history.page),
        }
      : {},
  [HistorySearchParams.QUERY]: (history) => {
    // Avoid empty query but allow empty string
    if (isNullOrUndefined(history.q)) {
      return {};
    }
    return {
      query: history.q,
    };
  },
  [HistorySearchParams.FACETS_FILTERS]: (history) => {
    if (!history.facetsFilters) {
      return {};
    }
    // we split back the facetsFilters expression to its sub components
    // parameter value is facet1:(value1 OR value2) AND facet2:(value3 OR value4)
    const selectedTermsByFacet = history.facetsFilters
      .split(QueryOperator.AND)
      .reduce((acc, filter) => {
        const [key, value] = filter.split(':');
        acc[key] = removeParenthesis(value).split(QueryOperator.OR);
        return acc;
      }, {} as Record<string, string[]>);

    return {
      selectedTermsByFacet,
    };
  },
};
/**
 * Mixin to handle the history of the search
 * It exists to have the logic of the history in a single place
 * It has to be inherited by SearchaliciousSearchMixin to implement _facetsNodes and _facetsFilters functionss
 * @param superClass
 * @constructor
 */
export const SearchaliciousHistoryMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  class SearchaliciousHistoryMixinClass extends superClass {
    /**
     * Query that will be sent to searchalicious
     */
    @property({attribute: false})
    query = '';

    /**
     * The name of this search
     */
    @property()
    name = 'searchalicious';

    _facetsNodes = (): SearchaliciousFacets[] => {
      throw new Error('Method not implemented.');
    };

    _facetsFilters = (): string => {
      throw new Error('Method not implemented.');
    };

    /**
     * Convert the URL params to the original values
     * It will be used to set the values from the URL
     * @param params
     */
    convertHistoryParamsToValues = (params: URLSearchParams): HistoryOutput => {
      const values: HistoryOutput = {};
      const history = removeParamPrefixes(
        Object.fromEntries(params),
        this.name
      );
      for (const key of SEARCH_PARAMS) {
        Object.assign(values, HISTORY_VALUES[key](history));
      }
      return values;
    };

    /**
     * Set the values from the history
     * It will set the params from the URL params
     * @param values
     */
    setValuesFromHistory = (values: HistoryOutput) => {
      this.query = values.query ?? '';
      if (values.selectedTermsByFacet) {
        this._facetsNodes().forEach((facets) =>
          facets.setSelectedTermsByFacet(values.selectedTermsByFacet!)
        );
      }
    };

    /**
     * Build the history params from the current state
     * It will be used to update the URL when searching
     * @param params
     */
    buildHistoryParams = (params: BuildParamsOutput) => {
      return addParamPrefixes(
        {
          [HistorySearchParams.QUERY]: this.query,
          [HistorySearchParams.FACETS_FILTERS]: this._facetsFilters(),
          [HistorySearchParams.PAGE]: params.page,
        },
        this.name
      ) as HistoryParams;
    };

    /**
     * Set the values from the URL
     * It will set the values from the URL and return if a search should be launched
     */
    setParamFromUrl = () => {
      const params = new URLSearchParams(window.location.search);
      const values = this.convertHistoryParamsToValues(params);

      this.setValuesFromHistory(values);

      const launchSearch = !!Object.keys(values).length;
      return {
        launchSearch,
        values,
      };
    };
  }

  return SearchaliciousHistoryMixinClass as Constructor<SearchaliciousHistoryInterface> &
    T;
};
