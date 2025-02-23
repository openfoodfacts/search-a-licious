import {SearchaliciousBar} from '../search-bar';

import {fixture, assert, expect} from '@open-wc/testing';
import {html} from 'lit/static-html.js';

suite('searchalicious-bar', () => {
  test('is defined', () => {
    const el = document.createElement('searchalicious-bar');
    assert.instanceOf(el, SearchaliciousBar);
  });

  test('renders with default values', async () => {
    const el = await fixture(html` <searchalicious-bar></searchalicious-bar>`);
    assert.shadowDom.equal(
      el,
      `
      <div class="search-bar" part="wrapper">
        <input
          class="search-input"
          autocomplete="off"
          name="q"
          part="input"
          placeholder="Search..."
          type="text"
        >
        </div>
      </div>
    `
    );
    const input = el.shadowRoot!.querySelector('input');
    expect(input).to.have.value('');
    const bar = el as SearchaliciousBar;
    assert.equal(bar.query, '');
    assert.equal(bar.index, undefined);
  });

  test('renders with custom attributes', async () => {
    const el = await fixture(
      html` <searchalicious-bar
        placeholder="Try it !"
        index="foo"
      ></searchalicious-bar>`
    );
    //const input = (el.getElementsByTagName('input')[0] as HTMLInputElement);
    //assert.equal(input.value, 'fixme');
    assert.shadowDom.equal(
      el,
      `
       <div class="search-bar" part="wrapper">
          <input
            autocomplete="off"
            name="q"
            class="search-input"
            part="input"
            placeholder="Try it !"
            type="text"
          >
        </div>
    `
    );
    const bar = el as SearchaliciousBar;
    assert.equal(bar.query, '');
    assert.equal(bar.index, 'foo');
  });

  test('text input in query', async () => {
    const el = await fixture(html` <searchalicious-bar></searchalicious-bar>`);
    const input = el.shadowRoot!.querySelector('input');
    input!.value = 'test';
    input!.dispatchEvent(new Event('input'));
    const bar = el as SearchaliciousBar;
    assert.equal(bar.query, 'test');
  });

  test('_searchUrl computation', async () => {
    const el = await fixture(
      html` <searchalicious-bar index="foo"></searchalicious-bar>`
    );
    const input = el.shadowRoot!.querySelector('input');
    input!.value = 'test';
    input!.dispatchEvent(new Event('input'));
    const bar = el as SearchaliciousBar;
    const searchParams = (bar as any)['_searchUrl']();
    assert.equal(searchParams.searchUrl, '/search');
    console.log(searchParams.params);
    assert.deepEqual(searchParams.params, {
      boost_phrase: false,
      index_id: 'foo',
      langs: ['en'],
      page_size: '10',
      q: 'test',
    });
    assert.equal(
      (bar as any)._paramsToQueryStr(searchParams.params),
      'index_id=foo&langs=en&page_size=10&q=test'
    );
  });

  test('_searchUrl computation boost phrase', async () => {
    const el = await fixture(
      html` <searchalicious-bar index="foo" boost-phrase></searchalicious-bar>`
    );
    const input = el.shadowRoot!.querySelector('input');
    input!.value = 'test';
    input!.dispatchEvent(new Event('input'));
    const bar = el as SearchaliciousBar;
    const searchParams = (bar as any)['_searchUrl']();
    assert.equal(searchParams.searchUrl, '/search');
    assert.deepEqual(searchParams.params, {
      boost_phrase: true,
      index_id: 'foo',
      langs: ['en'],
      page_size: '10',
      q: 'test',
    });
    // not present in search query string
    assert.equal(
      (bar as any)._paramsToQueryStr(searchParams.params),
      'boost_phrase=true&index_id=foo&langs=en&page_size=10&q=test'
    );
  });
});
