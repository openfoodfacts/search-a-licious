import {customElement, property} from 'lit/decorators.js';

import {SearchaliciousSortOption} from './search-sort';

/**
 * A component to add a specific sort option which is based upon a script
 *
 * See [How to use scripts](./how-to-use-scripts) for an introduction
 *
 * @event searchalicious-sort-option-selected - Fired when the sort option is selected.
 * @slot - the content is rendered as is.
 * This is the line displayed for the user to choose from sort options
 * @cssproperty - --sort-options-color - The text color of the sort options.
 * @cssproperty - --sort-options-hover-background-color - The background color of the sort options when hovered.
 * @csspart selected-marker - the text before the selected option
 * @csspart sort-option - the sort option itself, when not selected
 * @csspart sort-option-selected - the sort option itself, when selected
 * @property id - by default the id is based upon the script name.
 * If you have more than one element with the same value for the `script` attribute,
 * you must provide an id.
 */
@customElement('searchalicious-sort-script')
export class SearchaliciousSortScript extends SearchaliciousSortOption {
  /**
   * Name of the script to use for the sorting.
   *
   * This script must be registered in your backend configuration file.
   */
  @property()
  script?: string;

  /**
   * The parameters to pass to the scripts.
   *
   * If the script requires no parameters, this can be an empty Object `'{}'`
   *
   * It can be either:
   * - a JSON string containing parameters
   * - a local storage key, with prefix `local:`.
   *   In this case, the value of the key must be a JSON string.
   **/
  @property()
  parameters = '{}';

  override getDefaultId(): string {
    // we use the script name as id
    return `script-${this.script}`;
  }

  /**
   * Get the sort parameters according to parameters
   * @returns Object
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getScriptParameters(): Map<string, any> {
    if (this.parameters.startsWith('local:')) {
      const key = this.parameters.replace('local:', '');
      return JSON.parse(localStorage.getItem(key) ?? '{}');
    } else {
      return JSON.parse(this.parameters);
    }
  }

  /**
   * Properties to add to query to be able to sort on this specific script
   */
  override getSortParameters() {
    return {
      sort_by: this.script,
      sort_params: this.getScriptParameters(),
    };
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-sort-script': SearchaliciousSortScript;
  }
}
