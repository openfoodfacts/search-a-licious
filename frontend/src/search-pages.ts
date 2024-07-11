import {LitElement, html, css, nothing} from 'lit';
import {customElement, property, state} from 'lit/decorators.js';
import {repeat} from 'lit/directives/repeat.js';

import {SearchaliciousEvents} from './utils/enums';
import {SearchaliciousResultCtlMixin} from './mixins/search-results-ctl';
import {SearchResultDetail} from './signals';

// small utility to have a range
// inspired from https://stackoverflow.com/a/44957114/2886726
function _range(start: number, end: number): number[] {
  return Array(end - start)
    .fill(1)
    .map((_, idx) => start + idx);
}

/**
 * A component to display pagination for search results.
 */
@customElement('searchalicious-pages')
export class SearchaliciousPages extends SearchaliciousResultCtlMixin(
  LitElement
) {
  static override styles = css`
    ul {
      list-style-type: none;
      padding-left: 0;
      display: flex;
      justify-content: center;
    }
    li {
      display: inline-block;
      margin: 0 0.5rem;
      width: 30px;
      text-align: center;
    }
    li button {
      width: 100%;
    }
    li button:not(:disabled) {
      cursor: pointer;
    }
    .current button {
      font-weight: bold;
    }
  `;

  /**
   * Wether or not we should add the jump to first shortcuts
   */
  @property({attribute: 'display-first', type: Boolean})
  displayFirst = true;

  /**
   * Wether or not we should add the jump to end shortcuts
   */
  @property({attribute: 'display-last', type: Boolean})
  displayLast = true;

  /**
   * How many pages should we display as clickable links / buttons
   */
  @property({attribute: 'displayed-pages', type: Number})
  displayedPages = 5;

  /**
   * the first page to be displayed as a number
   */
  @state()
  _startRange?: number;

  /**
   * the last page to be displayed as a number
   */
  @state()
  _endRange?: number;

  /**
   * HTML to display when there are no results
   *
   * Can be overridden by a "no-results" slot
   */
  noResults = html``;

  /**
   * HTML to display before anysearch is launched
   *
   * Can be overridden by a "before-search" slot
   */
  beforeSearch = html``;

  override connectedCallback() {
    super.connectedCallback();

    this.searchResultDetailSignal.subscribe((searchResultDetail) => {
      this.handleResults(searchResultDetail);
    });
  }

  /**
   * Update state on search received
   */
  handleResults(searchResultDetail: SearchResultDetail) {
    [this._startRange, this._endRange] = this._computeRange(
      searchResultDetail.currentPage,
      searchResultDetail.pageCount
    );
    // this.requestUpdate();
  }

  /**
   * compute startRange and endRange
   */
  _computeRange(currentPage?: number, pageCount?: number) {
    if (!currentPage || !pageCount) {
      return [undefined, undefined];
    }
    // we try to display one page before
    let start =
      this.displayedPages > 2 ? Math.max(currentPage - 1, 1) : currentPage;
    const end = Math.min(start + this.displayedPages - 1, pageCount);
    if (end - start < this.displayedPages) {
      // near end of the list, show more pages before the end
      start = Math.max(1, end - this.displayedPages + 1);
    }
    return [start, end];
  }

  get _isFirstPage() {
    return Boolean(
      this.searchResultDetail.currentPage &&
        this.searchResultDetail.currentPage === 1
    );
  }
  get _isLastPage() {
    return Boolean(
      this.searchResultDetail.currentPage &&
        this.searchResultDetail.pageCount &&
        this.searchResultDetail.currentPage >= this.searchResultDetail.pageCount
    );
  }
  get _hasStartEllipsis() {
    return !!(this._startRange && this._startRange > 1);
  }
  get _hasEndEllipsis() {
    return !!(
      this._endRange &&
      this.searchResultDetail.pageCount &&
      this._endRange < this.searchResultDetail.pageCount
    );
  }
  get _displayPages() {
    if (!this._startRange || !this._endRange) {
      return [];
    }
    return _range(this._startRange, this._endRange + 1);
  }

  override render() {
    if (this.searchResultDetail.pageCount) {
      return this.renderPagination();
    } else if (this.searchResultDetail.isSearchLaunch) {
      return html`<slot name="no-results">${this.noResults}</slot>`;
    } else {
      return html`<slot name="before-search">${this.beforeSearch}</slot>`;
    }
  }

  /**
   * Render the pagination widget (when we have pages)
   */
  renderPagination() {
    return html`
      <nav part="nav">
        <ul part="pages">
          ${this.displayFirst
            ? html` <li @click=${this._firstPage} part="first">
                <slot name="first"
                  ><button ?disabled=${this._isFirstPage}>|&lt;</button></slot
                >
              </li>`
            : ''}
          <li @click=${this._prevPage} part="previous">
            <slot name="previous"
              ><button ?disabled=${this._isFirstPage}>&lt;</button></slot
            >
          </li>
          ${this._hasStartEllipsis
            ? html`<li part="start-ellipsis">
                <slot name="start-ellipsis">…</slot>
              </li>`
            : html`<li></li>`}
          ${repeat(
            this._displayPages,
            (page, _) => html` <li
              class="${page === this.searchResultDetail.currentPage!
                ? 'current'
                : ''}"
              part="${page === this.searchResultDetail.currentPage!
                ? 'current-'
                : ''}page"
            >
              <button @click=${() => this._askPageChange(page)}>${page}</button>
            </li>`
          )}
          ${this._hasEndEllipsis
            ? html`<li part="end-ellipsis">
                <slot name="end-ellipsis">…</slot>
              </li>`
            : html`<li></li>`}

          <li @click=${this._nextPage} part="next">
            <slot name="next"
              ><button ?disabled=${this._isLastPage}>&gt;</button></slot
            >
          </li>
          ${this.displayLast
            ? html` <li @click=${this._lastPage} part="last">
                <slot name="last"
                  ><button ?disabled=${this._isLastPage}>&gt;|</button></slot
                >
              </li>`
            : nothing}
        </ul>
      </nav>
    `;
  }

  _firstPage() {
    this._askPageChange(1);
  }

  _lastPage() {
    this._askPageChange(this.searchResultDetail.pageCount!);
  }

  _prevPage() {
    this._askPageChange(Math.max(1, this.searchResultDetail.currentPage! - 1));
  }

  _nextPage() {
    this._askPageChange(
      Math.min(
        this.searchResultDetail.currentPage! + 1,
        this.searchResultDetail.pageCount!
      )
    );
  }

  /**
   * Request a page change
   */
  _askPageChange(page: number) {
    if (page !== this.searchResultDetail.currentPage) {
      this.dispatchEvent(
        new CustomEvent(SearchaliciousEvents.CHANGE_PAGE, {
          detail: {
            searchName: this.searchName,
            page: page,
          },
          bubbles: true,
        })
      );
    }
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-pages': SearchaliciousPages;
  }
}
