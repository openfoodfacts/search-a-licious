import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {SearchaliciousSearchMixin} from './search-ctl';

/**
 * The search bar element
 *
 * This is the main component, it will enable the input of the search query
 * and it also manage all the search thanks to SearchaliciousSearchMixin inheritance.
 */
@customElement('searchalicious-bar')
export class SearchaliciousBar extends SearchaliciousSearchMixin(LitElement) {
  static override styles = css`
    :host {
      display: block;
      padding: 5px;
    }
  `;

  /**
   * Place holder in search bar
   */
  @property()
  placeholder = 'Search...';

  override render() {
    return html`
      <input
        type="text"
        name="q"
        @input=${this._onQueryChange}
        @keyup=${this._onKeyUp}
        .value=${this.query}
        placeholder=${this.placeholder}
        part="input"
      />
    `;
  }

  private _onQueryChange(event: Event) {
    this.query = (event.target as HTMLInputElement).value;
  }
  private _onKeyUp(event: Event) {
    const kbd_event = event as KeyboardEvent;
    if (kbd_event.key === 'Enter') {
      // launch search
      this.search();
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-bar': SearchaliciousBar;
  }
}
