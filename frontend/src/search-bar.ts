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
        .value=${this.query}
        placeholder=${this.placeholder}
      />
      <button @click=${this._onSearchClick} part="button">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          class="icon"
          aria-hidden="true"
          focusable="false"
        >
          <path
            d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"
          ></path>
          <path d="M0 0h24v24H0z" fill="none"></path>
        </svg>
      </button>
    `;
  }

  private _onQueryChange(event: Event) {
    this.query = (event.target as HTMLInputElement).value;
  }

  private _onSearchClick() {
    // launch search
    this.search();
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-bar': SearchaliciousBar;
  }
}
