export interface FacetItem {
  key: string;
  name: string;
}

export interface FacetInfo {
  name: string;
  // TODO: add other types if needed
  items: FacetItem[];
}

export interface FacetsInfos {
  [key: string]: FacetInfo;
}

export type ChartsInfos = Record<string, object>;