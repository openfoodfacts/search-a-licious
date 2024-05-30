/**
 * Every event as a searchName to tell which search-ctl/search-bar it targets
 */
export interface BaseSearchDetail {
  searchName: string;
}

/**
 * Detail of a search result
 */
export interface SearchResultDetail extends BaseSearchDetail {
  results: Object[];
  count: number;
  pageCount: number;
  pageSize: number;
  currentPage: number;
  facets: Object; // FIXME: we could be more precise
}

/**
 * detail for event asking for a page change
 */
export interface ChangePageDetail extends BaseSearchDetail {
  page: number;
}

/**
 * Event to ask for search to be launched
 */
export type LaunchSearchEvent = CustomEvent<BaseSearchDetail>;
/**
 * Event notifying a successful search result was received
 */
export type SearchResultEvent = CustomEvent<SearchResultDetail>;
/**
 * Event to ask for a new page of a search result
 */
export type ChangePageEvent = CustomEvent<ChangePageDetail>;
