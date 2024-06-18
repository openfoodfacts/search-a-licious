import {customElement} from 'lit/decorators.js';
import {css, html, LitElement} from 'lit';

@customElement('search-top-filters')
export class SearchTopFilters extends LitElement {
  static override styles = css`
    .search-top-filters {
      display: flex;
      justify-content: space-between;
      gap: 1rem;
    }

    .search-top-filters-buttons {
      display: flex;
      gap: 0.5rem;
    }
  `;
  override render() {
    return html`
      <div class="search-top-filters">
        <div>16,935 results for “Apple”</div>
        <div class="search-top-filters-buttons">
          <button>Sort by</button>
          <button>Filter</button>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'search-top-filters': SearchTopFilters;
  }
}
