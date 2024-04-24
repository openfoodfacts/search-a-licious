export type SearchResultDetail = {
  searchName: string;
  results: Object[];
  count: number;
  pageCount: number;
};

export type SearchResultEvent = CustomEvent<SearchResultDetail>;
