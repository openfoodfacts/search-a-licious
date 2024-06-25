/**
 * This file defines constants as Enums to be used in the library
 */
export enum SearchaliciousEvents {
  LAUNCH_SEARCH = 'searchalicious-search',
  NEW_RESULT = 'searchalicious-result',
  CHANGE_PAGE = 'searchalicious-change-page',
  // events for autocomplete selection
  AUTOCOMPLETE_SUBMIT = 'searchalicious-autocomplete-submit',
  AUTOCOMPLETE_INPUT = 'searchalicious-autocomplete-input',
  // events for sort option selection
  SORT_OPTION_SELECTED = 'searchalicious-sort-option-selected',
  // askin for first search launch is a specific event
  LAUNCH_FIRST_SEARCH = 'searchalicious-launch-first-search',
  // event for opening or closing chart sidebar
  OPEN_CLOSE_CHART_SIDEBAR = 'searchalicious-open-close-chart-sidebar',
  // event for reducing or expanding the chart sidebar
  REDUCE_EXPAND_CHART_SIDEBAR = 'searchalicious-reduce-expand-chart-sidebar',
}

/**
 * This enum defines the basic events that can be used in components to dispatch events
 */
export enum BasicEvents {
  CLICK = 'click',
  CHANGE = 'change',
}

/**
 *  This enum defines the possible operators for the search query
 */
export enum QueryOperator {
  AND = ' AND ',
  OR = ' OR ',
}
