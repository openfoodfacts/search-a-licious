/**
 * This file defines constants as Enums to be used in the library
 */
export enum SearchaliciousEvents {
  LAUNCH_SEARCH = 'searchalicious-search',
  NEW_RESULT = 'searchalicious-result',
  CHANGE_PAGE = 'searchalicious-change-page',
  AUTOCOMPLETE_SUBMIT = 'searchalicious-autocomplete-submit',
  AUTOCOMPLETE_INPUT = 'searchalicious-autocomplete-input',
  LAUNCH_FIRST_SEARCH = 'searchalicious-launch-first-search',
}

/**
 * This enum defines the basic events that can be used in components to dispatch events
 */
export enum BasicEvents {
  CLICK = 'click',
}

/**
 *  This enum defines the possible operators for the search query
 */
export enum QueryOperator {
  AND = ' AND ',
  OR = ' OR ',
}
