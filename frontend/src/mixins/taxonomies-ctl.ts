import {Constructor} from './utils';
import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';

export type TermOption = {
  id: string;
  text: string;
  taxonomy_name: string;
};

export type TaxomiesTermsResponse = {
  options: TermOption[];
};
export interface SearchaliciousTaxonomiesInterface {
  termsByTaxonomyId: Record<string, TermOption[]>;
  loadingByTaxonomyId: Record<string, boolean>;
  query: string;
  baseUrl: string;
  langs: string;
  index?: string;

  getTaxonomiesTerms(
    q: string,
    taxonomyNames: string[]
  ): Promise<TaxomiesTermsResponse>;
}
export const SearchaliciousTermsMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  class SearchaliciousTermsMixinClass extends superClass {
    @state()
    termsByTaxonomyId: Record<string, TermOption[]> = {};

    @state()
    loadingByTaxonomyId = {} as Record<string, boolean>;

    @property({attribute: false})
    query = '';

    @property()
    name = 'searchalicious';

    @property({attribute: 'base-url'})
    baseUrl = '/';

    @property()
    langs = 'en';

    _termsUrl(q: string, taxonomyNames: string[]) {
      const baseUrl = this.baseUrl.replace(/\/+$/, '');
      // http://localhost:8000/autocomplete?taxonomy_names=brand&q=anti&lang=en&size=10
      return `${baseUrl}/autocomplete?q=${q}&lang=${this.langs}&taxonomy_names=${taxonomyNames}&size=5`;
    }

    _setIsLoadingByTaxonomyNames(taxonomyNames: string[], isLoading: boolean) {
      taxonomyNames.forEach((taxonomyName) => {
        this.loadingByTaxonomyId[taxonomyName] = isLoading;
      });
    }
    getTaxonomiesTerms(
      q: string,
      taxonomyNames: string[]
    ): Promise<TaxomiesTermsResponse> {
      this._setIsLoadingByTaxonomyNames(taxonomyNames, true);
      return fetch(this._termsUrl(q, taxonomyNames), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
        .then((response) => {
          this._setIsLoadingByTaxonomyNames(taxonomyNames, false);

          if (!response.ok) {
            throw new Error('Network response was not ok');
          }
          return response.json() as Promise<TaxomiesTermsResponse>;
        })
        .then((response) => {
          this.termsByTaxonomyId = response.options.reduce((acc, option) => {
            if (!acc[option.taxonomy_name]) {
              acc[option.taxonomy_name] = [];
            }
            acc[option.taxonomy_name].push(option);
            return acc;
          }, {} as Record<string, TermOption[]>);
          return response;
        });
    }
  }
  return SearchaliciousTermsMixinClass as Constructor<SearchaliciousTaxonomiesInterface> &
    T;
};
