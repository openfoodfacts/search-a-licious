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
    window.history.pushState({}, '', '/');
    resetSignalToDefault();
  });

  teardown(() => {
    window.history.pushState({}, '', '/');
  });

  test('initializes properties correctly', async () => {
    const el = await fixture<DummySearchCtl>(
      html`<dummy-search-ctl></dummy-search-ctl>`
    );
    expect(el.name).to.equal(DEFAULT_SEARCH_NAME);
    expect(el.autoLaunch).to.be.false;
  });

  test('handles multi-search-name isolation', async () => {
    const el1 = await fixture<DummySearchCtl>(
      html`<dummy-search-ctl name="search1"></dummy-search-ctl>`
    );
    const el2 = await fixture<DummySearchCtl>(
      html`<dummy-search-ctl name="search2"></dummy-search-ctl>`
    );

    let el1Calls = 0;
    let el2Calls = 0;
    el1.updateSearchSignals = () => {
      el1Calls++;
    };
    el2.updateSearchSignals = () => {
      el2Calls++;
    };

    // event handlers are registered on the next animation frame
    await new Promise((resolve) => requestAnimationFrame(resolve));

    window.dispatchEvent(
      new CustomEvent(SearchaliciousEvents.FACET_SELECTED, {
        detail: {searchName: 'search1'},
      })
    );
    expect(el1Calls).to.equal(1);
    expect(el2Calls).to.equal(0);

    window.dispatchEvent(
      new CustomEvent(SearchaliciousEvents.FACET_SELECTED, {
        detail: {searchName: 'search2'},
      })
    );
    expect(el1Calls).to.equal(1);
    expect(el2Calls).to.equal(1);
  });
});
