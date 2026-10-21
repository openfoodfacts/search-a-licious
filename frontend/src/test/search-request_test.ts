import {fixture, assert, nextFrame} from '@open-wc/testing';
import {html} from 'lit/static-html.js';
import {SearchaliciousTermsFacet} from '../search-facets';
import {SearchaliciousBar} from '../search-bar';
import {SearchaliciousResults} from '../search-results';
import '../search-sort';
import '../search-count';
import '../search-pages';
import {isSearchLoading, searchResultDetail} from '../signals';
import {resetSignalToDefault} from './utils';

suite('search request lifecycle', () => {
  let originalFetch: typeof window.fetch;
  let bar: SearchaliciousBar;
  let results: SearchaliciousResults;
  let count: HTMLElement;
  let pages: HTMLElement;

  const response = (id: string) =>
    new Response(
      JSON.stringify({
        hits: [{id}],
        count: 1,
        page: 1,
        page_size: 10,
        page_count: 1,
        took: 1,
        facets: {},
        charts: {},
        is_count_exact: true,
      })
    );

  setup(async () => {
    originalFetch = window.fetch;
    resetSignalToDefault();
    window.history.replaceState({}, '', '/');
    window.fetch = async () => response('previous product');
    const container = await fixture(html`
      <div>
        <searchalicious-bar></searchalicious-bar>
        <searchalicious-results>
          <div slot="result"><li>\${result.id}</li></div>
        </searchalicious-results>
        <searchalicious-count></searchalicious-count>
        <searchalicious-pages></searchalicious-pages>
      </div>
    `);
    bar = container.querySelector('searchalicious-bar')!;
    results = container.querySelector('searchalicious-results')!;
    assert.instanceOf(bar, SearchaliciousBar);
    assert.instanceOf(results, SearchaliciousResults);
    count = container.querySelector('searchalicious-count')!;
    pages = container.querySelector('searchalicious-pages')!;
    // Let the controller's deferred URL initialization finish before seeding results.
    await nextFrame();
    await bar.search();
    await nextFrame();
    await results.updateComplete;

    assert.include(results.shadowRoot!.textContent!, 'previous product');
  });

  teardown(() => {
    window.fetch = originalFetch;
    isSearchLoading(bar.name).value = false;
    resetSignalToDefault();
    window.history.replaceState({}, '', '/');
  });

  test('replaces previous results with loading cards immediately', async () => {
    let finish!: (value: Response) => void;
    window.fetch = () => new Promise((resolve) => (finish = resolve));
    const pending = bar.search();
    try {
      await results.updateComplete;
      assert.deepEqual(searchResultDetail(bar.name).value.results, []);
      assert.notInclude(results.shadowRoot!.textContent!, 'previous product');
      assert.isNotNull(
        results.shadowRoot!.querySelector('[part="results-loading"]')
      );
    } finally {
      finish(response('next product'));
      await pending;
    }
  });

  const failures: [string, () => Promise<Response>][] = [
    ['HTTP 400', async () => new Response('{"errors": []}', {status: 400})],
    [
      'HTTP 500 HTML',
      async () => new Response('<h1>Internal error</h1>', {status: 500}),
    ],
    ['invalid JSON', async () => new Response('not JSON')],
    [
      'network error',
      async () => {
        throw new TypeError('Failed to fetch');
      },
    ],
  ];

  for (const [name, fail] of failures) {
    test(`clears stale data and recovers after ${name}`, async () => {
      window.fetch = fail;
      await bar.search();
      await results.updateComplete;
      assert.isFalse(isSearchLoading(bar.name).value);
      assert.deepEqual(searchResultDetail(bar.name).value.results, []);
      assert.isNotNull(results.shadowRoot!.querySelector('[role="alert"]'));
      assert.notInclude(results.shadowRoot!.textContent!, 'previous product');
      assert.notInclude(results.shadowRoot!.textContent!, 'No results found');
      assert.equal(count.shadowRoot!.textContent!.trim(), '');
      assert.equal(pages.shadowRoot!.textContent!.trim(), '');

      window.fetch = async () => response('recovered product');
      await bar.search();
      await results.updateComplete;
      assert.include(results.shadowRoot!.textContent!, 'recovered product');
      assert.isNull(results.shadowRoot!.querySelector('[role="alert"]'));
      assert.equal(bar.pageSize, 10);
    });
  }

  test('keeps the spinner while a newer request is still pending', async () => {
    const finish: ((value: Response) => void)[] = [];
    window.fetch = () => new Promise((resolve) => finish.push(resolve));
    const old = bar.search();
    const latest = bar.search();
    finish[0](response('obsolete product'));
    await old;
    assert.isTrue(isSearchLoading(bar.name).value);
    assert.deepEqual(searchResultDetail(bar.name).value.results, []);
    finish[1](response('latest product'));
    await latest;
    assert.isFalse(isSearchLoading(bar.name).value);
    assert.deepEqual(searchResultDetail(bar.name).value.results, [
      {id: 'latest product'},
    ]);
  });

  test('ignores an obsolete response whose JSON body arrives late', async () => {
    const body = await response('obsolete product').text();
    let controller!: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({
      start(value) {
        controller = value;
      },
    });
    window.fetch = async () => new Response(stream);
    const old = bar.search();
    await Promise.resolve();
    assert.isTrue(stream.locked);
    window.fetch = async () => response('latest product');
    await bar.search();
    controller.enqueue(new TextEncoder().encode(body));
    controller.close();
    await old;
    assert.deepEqual(searchResultDetail(bar.name).value.results, [
      {id: 'latest product'},
    ]);
  });

  test('keeps independent search results when another named search fails', async () => {
    const other = await fixture<SearchaliciousBar>(html`
      <searchalicious-bar name="other-search"></searchalicious-bar>
    `);
    window.fetch = async () => new Response('Unavailable', {status: 503});
    await other.search();
    assert.deepEqual(searchResultDetail(bar.name).value.results, [
      {id: 'previous product'},
    ]);
    assert.isTrue(searchResultDetail(other.name).value.error);
    assert.isFalse(isSearchLoading(other.name).value);
  });

  test('allows a custom error message while preserving the alert', async () => {
    const message = document.createElement('span');
    message.slot = 'error';
    message.textContent = 'The search service is unavailable.';
    results.append(message);
    window.fetch = async () => new Response('Unavailable', {status: 503});
    await bar.search();
    await results.updateComplete;
    const slot = results.shadowRoot!.querySelector<HTMLSlotElement>(
      '[role="alert"] slot'
    )!;
    assert.deepEqual(slot.assignedElements(), [message]);
  });

  for (const obsoleteFails of [false, true]) {
    test(`ignores an obsolete ${
      obsoleteFails ? 'failed' : 'successful'
    } request`, async () => {
      let finish!: (value: Response) => void;
      let fail!: (error: Error) => void;
      window.fetch = () =>
        new Promise((resolve, reject) => {
          finish = resolve;
          fail = reject;
        });
      const previous = bar.search();
      window.fetch = async () => response('latest product');
      await bar.search();
      if (obsoleteFails) {
        fail(new TypeError('obsolete failure'));
      } else {
        finish(response('obsolete product'));
      }
      await previous;
      await results.updateComplete;
      assert.include(results.shadowRoot!.textContent!, 'latest product');
      assert.notInclude(results.shadowRoot!.textContent!, 'obsolete product');
      assert.isNull(results.shadowRoot!.querySelector('[role="alert"]'));
      assert.isFalse(isSearchLoading(bar.name).value);
    });
  }

  test('retains the query and selected facets for retry after a failure', async () => {
    const facets = await fixture(html`
      <searchalicious-facets>
        <searchalicious-facet-terms
          name="labels_tags"
        ></searchalicious-facet-terms>
      </searchalicious-facets>
    `);
    const facet = facets.querySelector(
      'searchalicious-facet-terms'
    ) as SearchaliciousTermsFacet;
    searchResultDetail(bar.name).value = {
      ...searchResultDetail(bar.name).value,
      facets: {
        labels_tags: {
          name: 'Labels',
          items: [
            {key: 'en:organic', name: 'Organic', count: 1, selected: false},
          ],
        },
      },
    };
    await nextFrame();
    assert.instanceOf(facet, SearchaliciousTermsFacet);
    facet.setSelectedTerms(['en:organic']);
    bar.query = 'apples';
    const queries: string[] = [];
    window.fetch = async (url) => {
      queries.push(
        new URL(String(url), window.location.href).searchParams.get('q')!
      );
      return new Response('Unavailable', {status: 503});
    };
    await bar.search();
    await nextFrame();
    assert.equal(bar.query, 'apples');
    assert.equal(facet.searchFilter(), 'labels_tags:"en:organic"');
    await bar.search();
    assert.lengthOf(queries, 2);
    assert.include(queries[0], 'apples');
    assert.include(queries[0], 'labels_tags:"en:organic"');
    assert.equal(queries[1], queries[0]);
  });

  test('renders a visible error without horizontal overflow', async () => {
    window.fetch = async () => new Response('Unavailable', {status: 503});
    await bar.search();
    await results.updateComplete;
    const alert =
      results.shadowRoot!.querySelector<HTMLElement>('[role="alert"]')!;
    assert.include(alert.textContent!, 'Search failed. Please try again.');
    assert.isAbove(alert.getBoundingClientRect().height, 0);
    assert.isAtMost(document.documentElement.scrollWidth, window.innerWidth);
  });

  test('handles failures for sorted POST searches', async () => {
    await fixture(html`
      <searchalicious-sort>
        <searchalicious-sort-field
          field="code"
          selected
        ></searchalicious-sort-field>
      </searchalicious-sort>
    `);
    let method: string | undefined;
    window.fetch = async (_url, init) => {
      method = init?.method;
      return new Response('Unavailable', {status: 503});
    };
    await bar.search();
    await results.updateComplete;
    assert.equal(method, 'POST');
    assert.isFalse(isSearchLoading(bar.name).value);
    assert.isNotNull(results.shadowRoot!.querySelector('[role="alert"]'));
  });
});
