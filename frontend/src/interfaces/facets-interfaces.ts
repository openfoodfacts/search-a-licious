import {LitElement} from 'lit';

export interface SearchaliciousFacetsInterface extends LitElement {
  setSelectedTermsByFacet(value: Record<string, string[]>): void;
  selectTermByTaxonomy(taxonomy: string, term: string): boolean;
}
