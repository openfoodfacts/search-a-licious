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
  input: string;
  name: string;
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
  /** fuzziness to ask for, if any */
  readonly termsFuzziness: number | undefined;

  termLabel(term: TermOption): string;

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
    isTermsLoading = false;

    @property({attribute: 'base-url'})
    taxonomiesBaseUrl = '/';

    /**
     * langs to get suggestion from.
     *
     * Must be implementetd in  child class
     */
    get langs(): string {
      throw new Error('langs must be defined in child class');
    }

    /**
     * Fuzziness to ask for, if any.
     *
     * Child classes may override it, no fuzziness is asked by default.
     */
    get termsFuzziness(): number | undefined {
      return undefined;
    }

    termLabel(term: TermOption): string {
      return (
        term.text +
        (term.name && term.name != term.text ? ` (${term.name})` : '')
      );
    }

    /**
     * build URL to search taxonomies terms from input
     * @param {string} q - The query string.
     * @param {string[]} taxonomyNames - The taxonomy names.
     * @returns {string} - The terms URL.
     */
    _termsUrl(q: string, taxonomyNames: string[]) {
      const baseUrl = this.taxonomiesBaseUrl.replace(/\/+$/, '');
      // URLSearchParams encodes values: "M&M" must not become "M"
      const params = new URLSearchParams({
        q: q,
        langs: this.langs,
        taxonomy_names: taxonomyNames.join(','),
        size: '5',
      });
      const fuzziness = this.termsFuzziness;
      if (fuzziness !== undefined) {
        params.set('fuzziness', String(fuzziness));
      }
      return `${baseUrl}/autocomplete?${params}`;
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
      // get the version of the terms for each taxonomy
      const version = this.incrementVersion();
      if (!q) {
        // nothing to suggest: forget previous terms and pending requests
        this.terms = [];
        this.isTermsLoading = false;
        return Promise.resolve({options: []});
      }
      this.isTermsLoading = true;

      return fetch(this._termsUrl(q, taxonomyNames), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(
              `Network response was not ok (HTTP ${response.status})`
            );
          }
          return response.json() as Promise<TaxomiesTermsResponse>;
        })
        .then((response) => {
          if (this.isLatestVersion(version)) {
            // this is the legitimate suggestion request, loading finished
            this.terms = response.options;
            this.isTermsLoading = false;
          }
          // otherwise another suggestion request was launched in the mean time,
          // we give up on updating the state
          return response;
        })
        .catch((error) => {
          if (this.isLatestVersion(version)) {
            // do not stay loading forever, nor show terms of another input
            this.terms = [];
            this.isTermsLoading = false;
          }
          throw error;
        });
    }
  }
  return SearchaliciousTermsMixinClass as Constructor<SearchaliciousTaxonomiesInterface> &
    T;
};
