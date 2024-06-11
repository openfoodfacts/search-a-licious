import {Constructor} from './utils';
import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';

/**
 * Type for term options.
 */
export type TermOption = {
  id: string;
  text: string;
  taxonomy_name: string;
};

/**
 * Type for taxonomies terms response.
 */
export type TaxomiesTermsResponse = {
  options: TermOption[];
};

/**
 * Interface for the SearchaliciousTaxonomies.
 */
export interface SearchaliciousTaxonomiesInterface {
  termsByTaxonomyId: Record<string, TermOption[]>;
  loadingByTaxonomyId: Record<string, boolean>;
  taxonomiesBaseUrl: string;
  langs: string;

  /**
   * Method to get taxonomies terms.
   * @param {string} q - The query string.
   * @param {string[]} taxonomyNames - The taxonomy names.
   * @returns {Promise<TaxomiesTermsResponse>} - The promise of taxonomies terms response.
   */
  getTaxonomiesTerms(
    q: string,
    taxonomyNames: string[]
  ): Promise<TaxomiesTermsResponse>;
}

/**
 * A mixin class for Searchalicious terms.
 * @param {Constructor<LitElement>} superClass - The superclass to extend from.
 * @returns {Constructor<SearchaliciousTaxonomiesInterface> & T} - The extended class with Searchalicious terms functionality.
 */
export const SearchaliciousTermsMixin = <T extends Constructor<LitElement>>(
  superClass: T
): Constructor<SearchaliciousTaxonomiesInterface> & T => {
  class SearchaliciousTermsMixinClass extends superClass {
    @state()
    termsByTaxonomyId: Record<string, TermOption[]> = {};

    @state()
    loadingByTaxonomyId = {} as Record<string, boolean>;

    @property({attribute: 'base-url'})
    taxonomiesBaseUrl = '/';

    @property()
    langs = 'en';

    /**
     * Method to get terms URL.
     * @param {string} q - The query string.
     * @param {string[]} taxonomyNames - The taxonomy names.
     * @returns {string} - The terms URL.
     */
    _termsUrl(q: string, taxonomyNames: string[]) {
      const baseUrl = this.taxonomiesBaseUrl.replace(/\/+$/, '');
      return `${baseUrl}/autocomplete?q=${q}&lang=${this.langs}&taxonomy_names=${taxonomyNames}&size=5`;
    }

    /**
     * Method to set loading state by taxonomy names.
     * @param {string[]} taxonomyNames - The taxonomy names.
     * @param {boolean} isLoading - The loading state.
     */
    _setIsLoadingByTaxonomyNames(taxonomyNames: string[], isLoading: boolean) {
      taxonomyNames.forEach((taxonomyName) => {
        this.loadingByTaxonomyId[taxonomyName] = isLoading;
      });
    }

    /**
     * Method to get taxonomies terms.
     * @param {string} q - The query string.
     * @param {string[]} taxonomyNames - The taxonomy names.
     * @returns {Promise<TaxomiesTermsResponse>} - The promise of taxonomies terms response.
     */
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
