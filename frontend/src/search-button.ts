import {css, html, LitElement, nothing} from 'lit';
import {customElement} from 'lit/decorators.js';
import {searchBarInputAndButtonStyle} from './css/header';
import {isSearchChanged} from './signals';
import {localized, msg} from '@lit/localize';
import {SignalWatcher} from '@lit-labs/preact-signals';
import {SearchActionMixin} from './mixins/search-action';

/**
 * An optional search button element that launch the search.
 *
 * @slot - goes in button contents, default to "Search" string
 */
@customElement('searchalicious-button')
@localized()
export class SearchaliciousButton extends SignalWatcher(
  SearchActionMixin(LitElement)
) {
  static override styles = [
    searchBarInputAndButtonStyle,
    css`
      button {
        background-color: var(--search-button-background-color, #341100);
        border-radius: 0px 1000px 1000px 0px;
        padding: 0.4rem 0.5rem;
        margin: 0;
        border: 0;
        z-index: 2;
        cursor: pointer;
      }

      .button-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
        color: var(--searchalicious-button-text-color, white);
      }

      .button-content span {
        margin-right: 0.5rem;
        margin-left: 0.3rem;
      }
    `,
  ];

  /**
   * the search we should trigger,
   * this corresponds to `name` attribute of corresponding search-bar
   */

  override render() {
    return html`
      <button
        @click=${this._launchSearch}
        @keyup=${this._onKeyUp}
        part="button"
        role="button"
        class="search-button"
      >
        <slot>
          <div class="button-content">
            <searchalicious-icon-search></searchalicious-icon-search>
            ${isSearchChanged.value
              ? html`<span>${msg('Search', {desc: 'Search button'})}</span>`
              : nothing}
          </div>
        </slot>
      </button>
    `;
  }

  private _onKeyUp(event: Event) {
    const kbd_event = event as KeyboardEvent;
    if (kbd_event.key === 'Enter') {
      this._launchSearch();
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-button': SearchaliciousButton;
  }
}
