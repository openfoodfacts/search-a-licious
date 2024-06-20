import {SearchaliciousPages} from '../search-pages';
import {DEFAULT_SEARCH_NAME} from '../utils/constants';
import {SearchaliciousEvents} from '../utils/enums';
import {SearchResultDetail, SearchResultEvent} from '../events';

import {fixture, assert} from '@open-wc/testing';
import {html} from 'lit/static-html.js';

suite('searchalicious-pages', () => {
  // helper to simulate a search result
  const emitSearchResult = (
    el: SearchaliciousPages,
    currentPage: number,
    pageCount: number
  ) => {
    const detail: SearchResultDetail = {
      searchName: DEFAULT_SEARCH_NAME,
      results: [], // we don't really care
      count: Math.ceil(pageCount / 10),
      pageCount: pageCount,
      currentPage: currentPage,
      pageSize: 10,
      facets: {},
    };
    el._handleResults(
      new CustomEvent(SearchaliciousEvents.NEW_RESULT, {
        bubbles: true,
        composed: true,
        detail: detail,
      }) as SearchResultEvent
    );
  };
  // render pagination as txt
  const asTxt = (el: SearchaliciousPages) =>
    el.shadowRoot!.textContent!.replace(/\s+/g, ' ').trim();

  test('is defined', () => {
    const el = document.createElement('searchalicious-pages');
    assert.instanceOf(el, SearchaliciousPages);
  });

  test('renders with default values', async () => {
    const el = (await fixture(
      html`<searchalicious-pages></searchalicious-pages>`
    )) as SearchaliciousPages;
    // empty at first
    assert.equal(el.searchLaunched, false);
    assert.shadowDom.equal(el, '<slot name="before-search"></slot>');
    // emit search result
    emitSearchResult(el, 1, 100);
    await el.updateComplete;
    assert.equal(el.searchLaunched, true);
    assert.shadowDom.equal(
      el,
      `
      <nav part="nav">
        <ul part="pages">
          <li part="first">
            <slot name="first">
              <button disabled="">
                |&lt;
              </button>
            </slot>
          </li>
          <li part="previous">
            <slot name="previous">
              <button disabled="">
                &lt;
              </button>
            </slot>
          </li>
          <li
            class="current"
            part="current-page"
          >
            <button>
              1
            </button>
          </li>
          <li part="page">
            <button>
              2
            </button>
          </li>
          <li part="page">
            <button>
              3
            </button>
          </li>
          <li part="page">
            <button>
              4
            </button>
          </li>
          <li part="page">
            <button>
              5
            </button>
          </li>
          <li part="end-ellipsis">
            <slot name="end-ellipsis">
              …
            </slot>
          </li>
          <li part="next">
            <slot name="next">
              <button>
                &gt;
              </button>
            </slot>
          </li>
          <li part="last">
            <slot name="last">
              <button>
                &gt;|
              </button>
            </slot>
          </li>
        </ul>
      </nav>`
    );
    // emit an empty search result
    emitSearchResult(el, 1, 0);
    await el.updateComplete;
    assert.equal(el.searchLaunched, true);
    assert.deepEqual(el._pageCount, 0);
    assert.shadowDom.equal(el, '<slot name="no-results"></slot>');
  });
  test('render with specific before search', async () => {
    const el = (await fixture(html`<searchalicious-pages>
      <p slot="before-search">No pages yet !</p>
    </searchalicious-pages>`)) as SearchaliciousPages;
    assert.shadowDom.equal(el, `<slot name="before-search"></slot>`);
  });
  test('render with specific no results', async () => {
    const el = (await fixture(html`<searchalicious-pages>
      <p slot="no-results">No pages at all !</span></p>
    </searchalicious-pages>`)) as SearchaliciousPages;
    // emit an empty search result
    emitSearchResult(el, 1, 0);
    await el.updateComplete;
    assert.shadowDom.equal(el, `<slot name="no-results"></slot>`);
  });
  test('test render and navigate pages', async () => {
    const el = (await fixture(html`<searchalicious-pages>
    </searchalicious-pages>`)) as SearchaliciousPages;
    emitSearchResult(el, 1, 100);
    await el.updateComplete;
    assert.isOk(el._isFirstPage());
    assert.isNotOk(el._isLastPage());
    assert.equal(asTxt(el), '|< < 1 2 3 4 5 … > >|');
    emitSearchResult(el, 2, 100);
    await el.updateComplete;
    assert.isNotOk(el._isFirstPage());
    assert.isNotOk(el._isLastPage());
    assert.equal(asTxt(el), '|< < 1 2 3 4 5 … > >|');
    emitSearchResult(el, 3, 100);
    await el.updateComplete;
    assert.isNotOk(el._isFirstPage());
    assert.isNotOk(el._isLastPage());
    assert.equal(asTxt(el), '|< < … 2 3 4 5 6 … > >|');
    emitSearchResult(el, 25, 100);
    await el.updateComplete;
    assert.isNotOk(el._isFirstPage());
    assert.isNotOk(el._isLastPage());
    assert.equal(asTxt(el), '|< < … 24 25 26 27 28 … > >|');
    emitSearchResult(el, 98, 100);
    await el.updateComplete;
    assert.isNotOk(el._isFirstPage());
    assert.isNotOk(el._isLastPage());
    assert.equal(asTxt(el), '|< < … 96 97 98 99 100 > >|');
    emitSearchResult(el, 100, 100);
    await el.updateComplete;
    assert.isNotOk(el._isFirstPage());
    assert.isOk(el._isLastPage());
    assert.equal(asTxt(el), '|< < … 96 97 98 99 100 > >|');
  });
  test('test render pages different displayedPages is 1', async () => {
    const el = (await fixture(html`<searchalicious-pages displayed-pages="1">
    </searchalicious-pages>`)) as SearchaliciousPages;
    emitSearchResult(el, 1, 100);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < 1 … > >|');
    emitSearchResult(el, 25, 100);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < … 25 … > >|');
    emitSearchResult(el, 100, 100);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < … 100 > >|');
  });
  test('test render pages different displayedPages is 1', async () => {
    const el = (await fixture(html`<searchalicious-pages displayed-pages="1">
    </searchalicious-pages>`)) as SearchaliciousPages;
    emitSearchResult(el, 1, 100);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < 1 … > >|');
    emitSearchResult(el, 25, 100);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < … 25 … > >|');
    emitSearchResult(el, 100, 100);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < … 100 > >|');
  });
  test('test render pages different displayedPages is 3', async () => {
    const el = (await fixture(html`<searchalicious-pages displayed-pages="3">
    </searchalicious-pages>`)) as SearchaliciousPages;
    emitSearchResult(el, 1, 100);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < 1 2 3 … > >|');
    emitSearchResult(el, 25, 100);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < … 24 25 26 … > >|');
    emitSearchResult(el, 100, 100);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < … 98 99 100 > >|');
  });
  test('test render pages not many results', async () => {
    const el = (await fixture(html`<searchalicious-pages displayed-pages="5">
    </searchalicious-pages>`)) as SearchaliciousPages;
    emitSearchResult(el, 1, 1);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < 1 > >|');
    emitSearchResult(el, 1, 2);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < 1 2 > >|');
    emitSearchResult(el, 1, 5);
    await el.updateComplete;
    assert.equal(asTxt(el), '|< < 1 2 3 4 5 > >|');
  });
});
