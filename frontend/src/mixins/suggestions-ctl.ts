import {Constructor} from './utils';
import {LitElement} from 'lit';
import {property, state} from 'lit/decorators.js';
import {VersioningMixin, VersioningMixinInterface} from './versioning';

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
export interface SearchaliciousTaxonomiesInterface
  extends VersioningMixinInterface {
  terms: TermOption[];
  isTermsLoading: boolean;
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
 * It allows to get taxonomies terms and store them in termsByTaxonomyId.
 * @param {Constructor<LitElement>} superClass - The superclass to extend from.
 * @returns {Constructor<SearchaliciousTaxonomiesInterface> & T} - The extended class with Searchalicious terms functionality.
 */
export const SearchaliciousTermsMixin = <T extends Constructor<LitElement>>(
  superClass: T
): Constructor<SearchaliciousTaxonomiesInterface> & T => {
  class SearchaliciousTermsMixinClass extends VersioningMixin(superClass) {
    // this olds terms corresponding to current input for each taxonomy
    @state()
    terms: TermOption[] = [];

    @state()
    isTermsLoading = {} as boolean;

    @property({attribute: 'base-url'})
    taxonomiesBaseUrl = '/';

    @property()
    langs = 'en';

    /**
     * build URL to search taxonomies terms from input
     * @param {string} q - The query string.
     * @param {string[]} taxonomyNames - The taxonomy names.
     * @returns {string} - The terms URL.
     */
    _termsUrl(q: string, taxonomyNames: string[]) {
      const baseUrl = this.taxonomiesBaseUrl.replace(/\/+$/, '');
      return `${baseUrl}/autocomplete?q=${q}&lang=${this.langs}&taxonomy_names=${taxonomyNames}&size=5`;
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
      this.isTermsLoading = true;
      // get the version of the terms for each taxonomy
      const version = this.incrementVersion();

      return fetch(this._termsUrl(q, taxonomyNames), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
        .then((response) => {
          this.isTermsLoading = false;
          if (!response.ok) {
            throw new Error('Network response was not ok');
          }
          return response.json() as Promise<TaxomiesTermsResponse>;
        })
        .then((response) => {
          if (!this.isLatestVersion(version)) {
            return response;
          }
          this.terms = response.options;
          return response;
        });
    }
  }
  return SearchaliciousTermsMixinClass as Constructor<SearchaliciousTaxonomiesInterface> &
    T;
};
