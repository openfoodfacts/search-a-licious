import {createContext} from '@lit/context';
import {SearchaliciousSuggesterInterface} from './suggestion-interfaces';
import {SearchaliciousSearchInterface} from './search-ctl-interfaces';

export interface SuggesterRegistryInterface {
  searchCtl: SearchaliciousSearchInterface;
  registerSuggester(suggester: SearchaliciousSuggesterInterface): void;
}

export const suggesterRegistryContext =
  createContext<SuggesterRegistryInterface>(
    'searchalicious-suggester-registry'
  );
