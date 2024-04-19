export type SearchResultDetail = {
  searchName: string;
  results: Object[];
  count: number;
  pageCount: number;
  pageSize: number;
  currentPage: number;
};

export type SearchResultEvent = CustomEvent<SearchResultDetail>;
