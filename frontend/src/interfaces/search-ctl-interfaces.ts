import {EventRegistrationInterface} from './events-interfaces';
import {SearchaliciousHistoryInterface} from '../interfaces/history-interfaces';
import {SearchaliciousFacetsInterface} from './facets-interfaces';

export interface SearchaliciousSearchInterface
  extends EventRegistrationInterface,
    SearchaliciousHistoryInterface {
  query: string;
  name: string;
  baseUrl: string;
  langs: string;
  index: string;
  pageSize: number;
  lastQuery?: string;
  lastFacetsFilters?: string;
  isQueryChanged: boolean;
  isFacetsChanged: boolean;
  isSearchChanged: boolean;
  canReset: boolean;

  updateSearchSignals(): void;
  search(): Promise<void>;
  relatedFacets(): SearchaliciousFacetsInterface[];
  relatedFacets(): SearchaliciousFacetsInterface[];
  _facetsFilters(): string;
  resetFacets(launchSearch?: boolean): void;
}

/**
 * An interface to be able to get the search controller corresponding to a component
 */
export interface SearchCtlGetInterface {
  getSearchCtl(): SearchaliciousSearchInterface;
}
