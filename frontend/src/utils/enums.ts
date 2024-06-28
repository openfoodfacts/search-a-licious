/**
 * This file defines constants as Enums to be used in the library
 */
export enum SearchaliciousEvents {
  // askin for first search launch is a specific event
  LAUNCH_FIRST_SEARCH = 'searchalicious-launch-first-search',
  LAUNCH_SEARCH = 'searchalicious-search',
  // event for reseting the search
  RESET_SEARCH = 'searchalicious-reset-search',

  NEW_RESULT = 'searchalicious-result',
  CHANGE_PAGE = 'searchalicious-change-page',
  // events for autocomplete selection
  AUTOCOMPLETE_SUBMIT = 'searchalicious-autocomplete-submit',
  AUTOCOMPLETE_INPUT = 'searchalicious-autocomplete-input',
  // events for sort option selection
  SORT_OPTION_SELECTED = 'searchalicious-sort-option-selected',

  // event for opening or closing chart sidebar
  CHANGE_CHART_SIDEBAR_STATE = 'searchalicious-change-chart-sidebar-state',
  // event for facet selection
  FACET_SELECTED = 'searchalicious-facet-selected',
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

export enum SideBarState {
  OPENED = 'opened',
  CLOSED = 'closed',
  EXPANDED = 'expanded',
}

/**
 * This enum defines the possible values for the search name property
 */
export enum SearchNameProperty {
  OFF = 'off',
  SEARCHALICIOUS = 'searchalicious',
}
