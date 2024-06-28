/**
 * Every event as a searchName to tell which search-ctl/search-bar it targets
 */
export interface BaseSearchDetail {
  searchName: string;
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
 * Event to ask for a new page of a search result
 */
export type ChangePageEvent = CustomEvent<ChangePageDetail>;
