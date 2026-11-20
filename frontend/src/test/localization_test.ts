// register the elements
import '../search-facets';
import '../search-sort';
import '../search-pages';
import '../search-chart';
import type {SearchaliciousTermsFacet} from '../search-facets';
import type {SearchaliciousPages} from '../search-pages';
import type {SearchaliciousDistributionChart} from '../search-chart';
import {setLocale} from '../localization/main';
import {FacetInfo} from '../interfaces/search-result-interfaces';

import {fixture, assert} from '@open-wc/testing';
import {html} from 'lit/static-html.js';
import {resetSignalToDefault} from './utils';

const textOf = (el: Element | ShadowRoot) =>
  el.textContent!.replace(/\s+/g, ' ').trim();

suite('localization of default texts', () => {
  setup(() => {
    resetSignalToDefault();
  });

  // always go back to the source locale
  teardown(async () => {
    await setLocale('en');
  });

  test('reset button title of a facet', async () => {
    const el = (await fixture(
      html`<searchalicious-facet-terms
        name="brands_tags"
      ></searchalicious-facet-terms>`
    )) as SearchaliciousTermsFacet;
    el.infos = {
      name: 'brands_tags',
      items: [{key: 'en:milka', name: 'Milka', count: 3, selected: false}],
      count_error_upper_bound: 0,
    } as unknown as FacetInfo;
    await el.updateComplete;
    const button = () =>
      el.shadowRoot!.querySelector('searchalicious-button-transparent')!;

    assert.equal(button().getAttribute('title'), 'Reset brands_tags');
    await setLocale('fr');
    await el.updateComplete;
    assert.equal(button().getAttribute('title'), 'Réinitialiser brands_tags');
  });

  test('sort button default label', async () => {
    const el = await fixture(html`<searchalicious-sort></searchalicious-sort>`);
    assert.equal(textOf(el.shadowRoot!.querySelector('button')!), 'Sort by ▾');
    await setLocale('fr');
    await (el as unknown as {updateComplete: Promise<boolean>}).updateComplete;
    assert.equal(
      textOf(el.shadowRoot!.querySelector('button')!),
      'Trier par ▾'
    );
  });

  test('pagination buttons have an accessible name', async () => {
    const el = (await fixture(
      html`<searchalicious-pages
        display-first
        display-last
      ></searchalicious-pages>`
    )) as SearchaliciousPages;
    el.searchResultDetailSignal.value = {
      results: [],
      count: 100,
      pageCount: 10,
      currentPage: 5,
      pageSize: 10,
      facets: {},
      charts: {},
      displayTime: 0,
      isCountExact: true,
      isSearchLaunch: true,
    };
    await el.updateComplete;
    const names = () =>
      ['first', 'previous', 'next', 'last'].map((part) =>
        el
          .shadowRoot!.querySelector(`li[part="${part}"] button`)!
          .getAttribute('aria-label')
      );
    assert.deepEqual(names(), [
      'First page',
      'Previous page',
      'Next page',
      'Last page',
    ]);
    await setLocale('fr');
    await el.updateComplete;
    assert.deepEqual(names(), [
      'Première page',
      'Page précédente',
      'Page suivante',
      'Dernière page',
    ]);
  });

  test('chart without data', async () => {
    const el = (await fixture(
      html`<searchalicious-distribution-chart></searchalicious-distribution-chart>`
    )) as SearchaliciousDistributionChart;
    // vega is not installed in tests, pretend it is
    el.vegaInstalled = true;
    el.requestUpdate();
    await el.updateComplete;
    assert.include(textOf(el.shadowRoot!), 'No data');
    await setLocale('fr');
    await el.updateComplete;
    assert.include(textOf(el.shadowRoot!), 'Aucune donnée');
  });
});
