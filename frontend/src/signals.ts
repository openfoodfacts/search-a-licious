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
 * Signals to indicate if the search is loading.
 */
const _isSearchLoading: Record<string, Signal> = {} as Record<
  string,
  Signal<boolean>
>;

/**
 * Function to get or create a signal by search name.
 * If the signal does not exist, it creates it.
 * @param signalsObject
 * @param searchName
 */
const _getOrCreateSignal = (
  signalsObject: Record<string, Signal>,
  searchName: string
) => {
  if (!(searchName in signalsObject)) {
    signalsObject[searchName] = signal(false);
  }
  return signalsObject[searchName];
};

/**
 * Function to get the signal to indicate if the search has changed.
 * It is use by reset-button to know if it should be displayed.
 * @param searchName
 */
export const canResetSearch = (searchName: string) => {
  return _getOrCreateSignal(_canResetSearch, searchName);
};

/**
 * Function to get the signal to indicate if the search has changed.
 * it is used by the search button to know if it should be displayed.
 * @param searchName
 */
export const isSearchChanged = (searchName: string) => {
  return _getOrCreateSignal(_isSearchChanged, searchName);
};

/**
 * Function to get the signal to indicate if the search is loading.
 * The search-results utilize this to determine whether the loading card should be displayed.
 * @param searchName
 */
export const isSearchLoading = (searchName: string) => {
  return _getOrCreateSignal(_isSearchLoading, searchName);
};
