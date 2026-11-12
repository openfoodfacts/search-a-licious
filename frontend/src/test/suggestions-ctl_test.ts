// registers the element
import '../search-suggester';
import type {SearchaliciousTaxonomySuggester} from '../search-suggester';
import {SearchaliciousSearchInterface} from '../interfaces/search-ctl-interfaces';

import {fixture, assert, expect} from '@open-wc/testing';
import {html} from 'lit/static-html.js';

type FetchCall = {
  url: string;
  resolve: (response: Response) => void;
  reject: (e: Error) => void;
};

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {status});

const option = (id: string, text: string) => ({
  id,
  text,
  input: 'x',
  name: text,
  taxonomy_name: 'categories',
});

suite('taxonomy suggestions requests', () => {
  const originalFetch = window.fetch;
  let calls: FetchCall[] = [];

  setup(() => {
    calls = [];
    window.fetch = ((url: string) =>
      new Promise<Response>((resolve, reject) => {
        calls.push({url: String(url), resolve, reject});
      })) as typeof window.fetch;
  });

  teardown(() => {
    window.fetch = originalFetch;
  });

  const suggester = async () => {
    const el = (await fixture(
      html`<searchalicious-taxonomy-suggest
        base-url="http://api.test/"
        taxonomies="categories,labels"
      ></searchalicious-taxonomy-suggest>`
    )) as SearchaliciousTaxonomySuggester;
    el.searchCtl = {langs: 'en,fr'} as SearchaliciousSearchInterface;
    return el;
  };

  const params = (call: FetchCall) => new URL(call.url).searchParams;

  test('encodes the query and the parameters', async () => {
    const el = await suggester();
    el.getSuggestions('M&M #1+2');
    assert.equal(calls.length, 1);
    const url = new URL(calls[0].url);
    assert.equal(url.origin + url.pathname, 'http://api.test/autocomplete');
    assert.equal(params(calls[0]).get('q'), 'M&M #1+2');
    assert.equal(params(calls[0]).get('langs'), 'en,fr');
    assert.equal(params(calls[0]).get('taxonomy_names'), 'categories,labels');
    assert.equal(params(calls[0]).get('size'), '5');
  });

  test('does not send fuzziness by default', async () => {
    const el = await suggester();
    el.getSuggestions('milk');
    assert.isFalse(params(calls[0]).has('fuzziness'));
  });

  test('sends fuzziness when it is set', async () => {
    const el = (await suggester()) as SearchaliciousTaxonomySuggester;
    el.fuzziness = 1;
    el.getSuggestions('milk');
    assert.equal(params(calls[0]).get('fuzziness'), '1');
    // 0 is a value too
    el.fuzziness = 0;
    el.getSuggestions('milk');
    assert.equal(params(calls[1]).get('fuzziness'), '0');
  });

  test('suggestions come from the response', async () => {
    const el = await suggester();
    const promise = el.getSuggestions('mil');
    assert.isTrue(el.isTermsLoading);
    calls[0].resolve(jsonResponse({options: [option('en:milk', 'Milk')]}));
    const suggestions = await promise;
    assert.isFalse(el.isTermsLoading);
    assert.equal(suggestions.length, 1);
    assert.equal(suggestions[0].value, 'milk');
    assert.equal(suggestions[0].id, 'en:milk');
    assert.equal(suggestions[0].input, 'mil');
  });

  test('an empty query makes no request and forgets old terms', async () => {
    const el = await suggester();
    const first = el.getSuggestions('mil');
    calls[0].resolve(jsonResponse({options: [option('en:milk', 'Milk')]}));
    await first;
    assert.equal(el.terms.length, 1);

    const suggestions = await el.getSuggestions('');
    assert.equal(calls.length, 1);
    assert.deepEqual(suggestions, []);
    assert.deepEqual(el.terms, []);
    assert.isFalse(el.isTermsLoading);
  });

  test('a network failure stops loading and rejects', async () => {
    const el = await suggester();
    const promise = el.getSuggestions('mil');
    assert.isTrue(el.isTermsLoading);
    calls[0].reject(new Error('offline'));
    let failed = false;
    await promise.catch(() => (failed = true));
    assert.isTrue(failed);
    assert.isFalse(el.isTermsLoading);
    assert.deepEqual(el.terms, []);
  });

  test('an error response stops loading and rejects', async () => {
    const el = await suggester();
    const promise = el.getSuggestions('mil');
    calls[0].resolve(jsonResponse({detail: 'oops'}, 500));
    let failed = false;
    await promise.catch(() => (failed = true));
    assert.isTrue(failed);
    assert.isFalse(el.isTermsLoading);
  });

  test('a late answer to an older request does not replace terms', async () => {
    const el = await suggester();
    const older = el.getSuggestions('mi');
    const newer = el.getSuggestions('milk');
    calls[1].resolve(jsonResponse({options: [option('en:milk', 'Milk')]}));
    await newer;
    calls[0].resolve(jsonResponse({options: [option('en:mint', 'Mint')]}));
    await older;
    expect(el.terms.map((t) => t.id)).to.deep.equal(['en:milk']);
    assert.isFalse(el.isTermsLoading);
  });

  test('loading goes on until the latest request ends', async () => {
    const el = await suggester();
    const older = el.getSuggestions('mi');
    const newer = el.getSuggestions('milk');
    calls[0].resolve(jsonResponse({options: []}));
    await older;
    assert.isTrue(el.isTermsLoading);
    calls[1].resolve(jsonResponse({options: []}));
    await newer;
    assert.isFalse(el.isTermsLoading);
  });
});
