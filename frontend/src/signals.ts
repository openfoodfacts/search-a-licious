import {signal} from '@lit-labs/preact-signals';

/**
 * Signal to indicate if we can reset the search.
 * It is use by reset-button to know if it should be displayed.
 */
export const canResetSearch = signal(false);

/**
 * Signal to indicate if the search has changed.
 * it is used by the search button to know if it should be displayed.
 */
export const isSearchChanged = signal(false);
