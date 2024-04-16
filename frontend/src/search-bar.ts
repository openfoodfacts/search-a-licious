import {LitElement, html, css} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {SearchaliciousSearchMixin} from './search-ctl';

/**
 * The search bar element.
 *
 */
@customElement('searchalicious-bar')
export class SearchaliciousBar extends SearchaliciousSearchMixin(LitElement) {
  static override styles = css`
    :host {
      display: block;
      border: solid 1px gray;
      padding: 16px;
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
