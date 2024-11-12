import {TemplateResult} from 'lit';

/**
 * Type for suggestion option.
 */
export type SuggestionSelectionOption = {
  /**
   * value assigned to this suggestion
   */
  value: string;
  /**
   * Label to display this suggestion
   */
  label: string;
  /**
   * Unique id for this suggestion
   *
   * It is important when we have multiple suggestions sources
   */
  id: string;
  /**
   * text that gave the suggestion
   *
   * It is important because we might do a suggestion on part of the searched terms
   */
  input: string;
};

/**
 * Type for a suggested option
 */
export type SuggestOption = SuggestionSelectionOption & {
  /**
   * source of this suggestion
   */
  source: SearchaliciousSuggesterInterface;
};

export interface SearchaliciousSuggesterInterface {
  getSuggestions(_value: string): Promise<SuggestOption[]>;
  selectSuggestion(_selected: SuggestionSelectionOption): void;
  renderSuggestion(_suggestion: SuggestOption, _index: number): TemplateResult;
}
