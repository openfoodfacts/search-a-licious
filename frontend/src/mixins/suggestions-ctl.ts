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
 * It allows to get taxonomies terms and store them in termsByTaxonomyId.
 * @param {Constructor<LitElement>} superClass - The superclass to extend from.
 * @returns {Constructor<SearchaliciousTaxonomiesInterface> & T} - The extended class with Searchalicious terms functionality.
 */
export const SearchaliciousTermsMixin = <T extends Constructor<LitElement>>(
  superClass: T
): Constructor<SearchaliciousTaxonomiesInterface> & T => {
  class SearchaliciousTermsMixinClass extends superClass {
    // this olds terms corresponding to current input for each taxonomy
    @property()
    termsByTaxonomyId: Record<string, TermOption[]> = {};

    @state()
    versionByTaxonomyId: Record<string, number> = {};

    @state()
    loadingByTaxonomyId = {} as Record<string, boolean>;

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
     * Method to set loading state by taxonomy names.
     * We support more than one taxonomy at once,
     * as suggest requests can target multiple taxonomies at once
     * @param {string[]} taxonomyNames - The taxonomy names.
     * @param {boolean} isLoading - The loading state.
     */
    _setIsLoadingByTaxonomyNames(taxonomyNames: string[], isLoading: boolean) {
      taxonomyNames.forEach((taxonomyName) => {
        this.loadingByTaxonomyId[taxonomyName] = isLoading;
      });
    }

    /**
     * Method to get versions by taxonomy id.
     * It returns the version of the terms for each taxonomy.
     * It is used to ignore responses that are older than the current version.
     * @param taxonomyNames
     */
    getVersionsByTaxonomyId(taxonomyNames: string[]): Record<string, number> {
      return taxonomyNames.reduce((acc, taxonomyName) => {
        acc[taxonomyName] =
          taxonomyName in this.versionByTaxonomyId
            ? this.versionByTaxonomyId[taxonomyName] + 1
            : 0;
        return acc;
      }, {} as Record<string, number>);
    }

    /**
     * Method to check if the version of the terms is newer.
     * @param taxonomyName
     * @param version
     */
    isANewerVersionOfTermsByTaxonomyId(
      taxonomyName: string,
      version: number
    ): boolean {
      return (
        this.versionByTaxonomyId[taxonomyName] === undefined ||
        this.versionByTaxonomyId[taxonomyName] < version
      );
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
      // get the version of the terms for each taxonomy
      const versionByTaxonomyId = this.getVersionsByTaxonomyId(taxonomyNames);

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
          // group terms by taxonomy id
          const termsByTaxonomyId = response.options.reduce((acc, option) => {
            if (!acc[option.taxonomy_name]) {
              acc[option.taxonomy_name] = [];
            }
            acc[option.taxonomy_name].push(option);
            return acc;
          }, {} as Record<string, TermOption[]>);

          // only update terms if the response is newer
          Object.entries(termsByTaxonomyId).forEach(([taxonomyName, terms]) => {
            if (
              this.isANewerVersionOfTermsByTaxonomyId(
                taxonomyName,
                versionByTaxonomyId[taxonomyName]
              )
            ) {
              this.versionByTaxonomyId[taxonomyName] =
                versionByTaxonomyId[taxonomyName];
              this.termsByTaxonomyId = {
                ...this.termsByTaxonomyId,
                [taxonomyName]: terms,
              };
            }
          });

          return response;
        });
    }
  }
  return SearchaliciousTermsMixinClass as Constructor<SearchaliciousTaxonomiesInterface> &
    T;
};
