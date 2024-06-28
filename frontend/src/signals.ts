import {Signal, signal} from '@lit-labs/preact-signals';
import {SearchNameProperty} from './utils/enums';

/**
 * Signals to indicate if the search can be reset.
 * It is store in object to be able to access it by search name.
 */
const _canResetSearch: Record<SearchNameProperty, Signal> = {} as Record<
  SearchNameProperty,
  Signal<boolean>
>;

/**
 * Signals to indicate if the search has changed.
 * It is store in object to be able to access it by search name.
 */
const _isSearchChanged: Record<SearchNameProperty, Signal> = {} as Record<
  SearchNameProperty,
  Signal<boolean>
>;

/**
 * Initialize the signals for each search name.
 */
for (const searchName of Object.values(SearchNameProperty)) {
  _canResetSearch[searchName as SearchNameProperty] = signal(false);
  _isSearchChanged[searchName as SearchNameProperty] = signal(false);
}

/**
 * Function to get the signal to indicate if the search has changed.
 * It is use by reset-button to know if it should be displayed.
 */
export const canResetSearch = (searchName: SearchNameProperty) => {
  return _canResetSearch[searchName];
};

/**
 * Functiin to get the signal to indicate if the search has changed.
 * it is used by the search button to know if it should be displayed.
 */
export const isSearchChanged = (searchName: SearchNameProperty) => {
  return _isSearchChanged[searchName];
};
