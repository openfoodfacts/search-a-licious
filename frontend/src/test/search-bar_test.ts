/**
 * @license
 * Copyright 2021 Google LLC
 * SPDX-License-Identifier: BSD-3-Clause
 */

import {SearchaliciousBar} from '../search-bar';

import {fixture, assert} from '@open-wc/testing';
import {html} from 'lit/static-html.js';

suite('searchalicious-bar', () => {
  test('is defined', () => {
    const el = document.createElement('searchalicious-bar');
    assert.instanceOf(el, SearchaliciousBar);
  });

  test('renders with default values', async () => {
    const el = await fixture(html`<searchalicious-bar></searchalicious-bar>`);
    //const input = (el.getElementsByTagName('input')[0] as HTMLInputElement);
    //assert.equal(input.value, 'fixme');
    assert.shadowDom.equal(
      el,
      `
      <input
        name="q"
        placeholder="Search..."
        type="text"
        >
    `
    );
  });
});
