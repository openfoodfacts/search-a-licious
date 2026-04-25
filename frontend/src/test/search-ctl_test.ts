import {fixture, html, expect} from '@open-wc/testing';
import {LitElement} from 'lit';
import {customElement, state} from 'lit/decorators.js';
import {SearchaliciousSearchMixin} from '../mixins/search-ctl';
import {SearchaliciousEvents} from '../utils/enums';
import {resetSignalToDefault} from './utils';
import {DEFAULT_SEARCH_NAME} from '../utils/constants';

@customElement('dummy-search-ctl')
class DummySearchCtl extends SearchaliciousSearchMixin(LitElement) {
  @state() autoLaunch = false;
  override baseUrl = 'http://localhost/api';
}

suite('SearchaliciousSearchMixin / search-ctl', () => {
  setup(() => {
    resetSignalToDefault();
  });

  teardown(() => {
    window.history.pushState({}, '', '/');
  });

  test('initializes properties correctly', async () => {
    const el = await fixture<DummySearchCtl>(html`<dummy-search-ctl></dummy-search-ctl>`);
    expect(el.name).to.equal(DEFAULT_SEARCH_NAME);
    expect(el.autoLaunch).to.be.false;
  });

  test('handles multi-search-name isolation', async () => {
    const el1 = await fixture<DummySearchCtl>(html`<dummy-search-ctl name="search1"></dummy-search-ctl>`);
    const el2 = await fixture<DummySearchCtl>(html`<dummy-search-ctl name="search2"></dummy-search-ctl>`);
    
    let el1Triggered = false;
    let el2Triggered = false;

    // Listen to signal that fetch initiates
    el1.addEventListener(SearchaliciousEvents.FACET_SELECTED, () => { el1Triggered = true; });
    el2.addEventListener(SearchaliciousEvents.FACET_SELECTED, () => { el2Triggered = true; });

    el1.dispatchEvent(new CustomEvent(SearchaliciousEvents.FACET_SELECTED, {
      detail: { searchName: 'search1' },
      bubbles: true,
      composed: true
    }));

    await el1.updateComplete;
    await el2.updateComplete;

    expect(el1Triggered).to.be.true;
    expect(el2Triggered).to.be.false;
  });
});
