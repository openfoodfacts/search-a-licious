import {SortParameters} from './sort-interfaces';
import {ChartSearchParam} from './chart-interfaces';

export interface SearchParameters extends SortParameters {
  q: string;
  boost_phrase: Boolean;
  langs: string[];
  page_size: string;
  page?: string;
  index_id?: string;
  facets?: string[];
  params?: string[];
  charts?: string | ChartSearchParam[];
}
