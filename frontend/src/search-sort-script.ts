import {customElement, property} from 'lit/decorators.js';

import {SearchaliciousSortOption} from './search-sort';

/**
 * A component to add a specific sort option which is based upon a script
 */
@customElement('searchalicious-sort-script')
export class SearchaliciousSortScript extends SearchaliciousSortOption {
  // Name of the script to use for the sorting
  @property()
  script?: string;

  /**
   * The parameters source.
   * It can be either a JSON string or local storage key, with prefix local:
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
