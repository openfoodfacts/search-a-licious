import {SearchaliciousButton} from '../search-button';

import {fixture, assert} from '@open-wc/testing';
import {html} from 'lit/static-html.js';

suite('searchalicious-button', () => {
  test('is defined', () => {
    const el = document.createElement('searchalicious-button');
    assert.instanceOf(el, SearchaliciousButton);
  });

  test('renders with default values', async () => {
    const el = await fixture(
      html`<searchalicious-button></searchalicious-button>`
    );
    assert.shadowDom.equal(
      el,
      `
      <button
        part="button"
        role="button"
        class="search-button">
          <div class="button-content">
            <slot name="icon"><searchalicious-icon-search></searchalicious-icon-search></slot>
            <slot></slot>
          </div>
      </button>
    `
    );
  });
});
