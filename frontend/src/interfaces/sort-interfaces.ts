export interface SortParameters {
  sort_by?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  sort_params?: Record<string, any>;
}

export interface SearchaliciousSortInterface {
  getSortParameters(): SortParameters | null;
  setSortOptionById(optionId: string | undefined): void;
}
