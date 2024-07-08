import {Signal, signal} from '@lit-labs/preact-signals';

/**
 * Signals to indicate if the search can be reset.
 * It is store in object to be able to access it by search name.
 */
const _canResetSearch: Record<string, Signal> = {} as Record<
  string,
  Signal<boolean>
>;

/**
 * Signals to indicate if the search has changed.
 * It is store in object to be able to access it by search name.
 */
const _isSearchChanged: Record<string, Signal> = {} as Record<
  string,
  Signal<boolean>
>;

/**
 * Search result as returned by a search request, payload of searchResult signal
 */
export type SearchResultDetail = {
  charts: Record<string, object>;
  count: number;
  currentPage: number;
  displayTime: number;
  facets: Object; // FIXME: we could be more precise
  isCountExact: boolean;
  isSearchLaunch: boolean;
  pageCount: number;
  pageSize: number;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  results: Record<string, any>[];
};

const _searchResultDetail: Record<
  string,
  Signal<SearchResultDetail>
> = {} as Record<string, Signal<SearchResultDetail>>;

/**
 * Payload for searchResult signal, before we launch any search
 *
 * isSearchLaunch is false
 */
export const getDefaultSearchResultDetail = () => ({
  charts: {},
  count: 0,
  currentPage: 0,
  displayTime: 0,
  facets: {},
  isCountExact: true,
  isSearchLaunch: false,
  pageCount: 0,
  pageSize: 0,
  results: [],
});
/**
 * Signals to indicate if the search is loading.
 */
const _isSearchLoading: Record<string, Signal> = {} as Record<
  string,
  Signal<boolean>
>;

/**
 * Function to get or create a signal by search name.
 * If the signal does not exist, it creates it using the default value.
 * @param signalsObject
 * @param searchName
 * @param defaultValue - default value in case it does not yet exists
 */
const _getOrCreateSignal = <T>(
  signalsObject: Record<string, Signal<T>>,
  searchName: string,
  defaultValue: T
) => {
  if (!(searchName in signalsObject)) {
    signalsObject[searchName] = signal(defaultValue);
  }
  return signalsObject[searchName];
};

/**
 * Function to get the signal to indicate if the search has changed.
 * It is use by reset-button to know if it should be displayed.
 * @param searchName
 */
export const canResetSearch = (searchName: string) => {
  return _getOrCreateSignal<boolean>(_canResetSearch, searchName, false);
};

/**
 * Function to get the signal to indicate if the search has changed.
 * it is used by the search button to know if it should be displayed.
 * @param searchName
 */
export const isSearchChanged = (searchName: string) => {
  return _getOrCreateSignal<boolean>(_isSearchChanged, searchName, false);
};

/**
 * Get the SearcResultDetail signal based on search name.
 *
 * If the no search was yet launch, return a detail corresponding to no search
 */
export const searchResultDetail = (searchName: string) => {
  return _getOrCreateSignal<SearchResultDetail>(
    _searchResultDetail,
    searchName,
    getDefaultSearchResultDetail()
  );
};

/**
 * Function to get the signal to indicate if the search is loading.
 * The search-results utilize this to determine whether the loading card should be displayed.
 * @param searchName
 */
export const isSearchLoading = (searchName: string) => {
  return _getOrCreateSignal(_isSearchLoading, searchName, false);
};
