import {html as litHtml} from 'lit';
// register the elements
import '../search-bar';
import '../search-autocomplete';
import type {SearchaliciousBar} from '../search-bar';
import type {SearchaliciousAutocomplete} from '../search-autocomplete';
import {SuggestOption} from '../interfaces/suggestion-interfaces';

import {fixture, assert} from '@open-wc/testing';
import {html} from 'lit/static-html.js';

const source = {
  getSuggestions: async () => [],
  selectSuggestion: async () => undefined,
  renderSuggestion: (option: SuggestOption) => litHtml`${option.label}`,
};

const option = (id: string): SuggestOption => ({
  id,
  value: id,
  label: `Label ${id}`,
  input: 'x',
  source: source as unknown as SuggestOption['source'],
});

const press = (input: HTMLInputElement, key: string) => {
  const event = new KeyboardEvent('keydown', {
    key,
    bubbles: true,
    cancelable: true,
  });
  input.dispatchEvent(event);
  return event;
};

suite('search bar suggestions accessibility', () => {
  const bar = async () => {
    const el = (await fixture(
      html`<searchalicious-bar></searchalicious-bar>`
    )) as SearchaliciousBar;
    // do not really search
    el.search = async () => undefined;
    el.query = 'x';
    el.visible = true;
    el.options = [option('a'), option('b'), option('c')];
    await el.updateComplete;
    return el;
  };
  const inputOf = (el: SearchaliciousBar) =>
    el.shadowRoot!.querySelector('input')!;

  test('input is a combobox controlling a listbox of options', async () => {
    const el = await bar();
    const input = inputOf(el);
    assert.equal(input.getAttribute('role'), 'combobox');
    assert.equal(input.getAttribute('aria-expanded'), 'true');
    assert.equal(input.getAttribute('aria-autocomplete'), 'list');
    const list = el.shadowRoot!.querySelector('ul')!;
    assert.equal(list.getAttribute('role'), 'listbox');
    assert.equal(input.getAttribute('aria-controls'), list.id);
    const options = list.querySelectorAll('li');
    assert.equal(options.length, 3);
    options.forEach((li) => assert.equal(li.getAttribute('role'), 'option'));
  });

  test('input is collapsed when there is nothing to show', async () => {
    const el = await bar();
    el.options = [];
    await el.updateComplete;
    const input = inputOf(el);
    assert.equal(input.getAttribute('aria-expanded'), 'false');
    assert.isFalse(input.hasAttribute('aria-activedescendant'));
    // no dangling reference to a list that is not there
    assert.isFalse(input.hasAttribute('aria-controls'));
    assert.isNull(el.shadowRoot!.querySelector('ul'));
  });

  test('arrow keys move the active option without moving the caret', async () => {
    const el = await bar();
    const input = inputOf(el);
    const down = press(input, 'ArrowDown');
    assert.isTrue(down.defaultPrevented);
    await el.updateComplete;
    assert.equal(input.getAttribute('aria-activedescendant'), 'suggestion-1');
    const items = el.shadowRoot!.querySelectorAll('li');
    assert.equal(items[0].getAttribute('aria-selected'), 'true');
    assert.equal(items[1].getAttribute('aria-selected'), 'false');

    assert.isTrue(press(input, 'ArrowUp').defaultPrevented);
    await el.updateComplete;
    assert.isFalse(input.hasAttribute('aria-activedescendant'));
  });

  test('an arrow key shows the suggestions again after they were closed', async () => {
    const el = await bar();
    el.visible = false;
    await el.updateComplete;
    assert.isNull(el.shadowRoot!.querySelector('ul'));
    press(inputOf(el), 'ArrowDown');
    await el.updateComplete;
    assert.isNotNull(el.shadowRoot!.querySelector('ul'));
  });

  test('enter on a stale highlighted index searches the typed text', async () => {
    const el = await bar();
    // the highlighted option does not exist anymore (list became shorter)
    el.currentIndex = 3;
    el.options = [option('a')];
    const input = inputOf(el);
    input.value = 'typed';
    let searched = 0;
    el.search = async () => {
      searched++;
    };
    press(input, 'Enter');
    assert.equal(searched, 1);
    assert.equal(el.query, 'typed');
  });

  test('escape forgets the highlighted option', async () => {
    const el = await bar();
    press(inputOf(el), 'ArrowDown');
    assert.equal(el.currentIndex, 1);
    press(inputOf(el), 'Escape');
    assert.equal(el.currentIndex, 0);
  });
});

suite('autocomplete accessibility', () => {
  const autocomplete = async () => {
    const el = (await fixture(
      html`<searchalicious-autocomplete
        input-name="add-term"
      ></searchalicious-autocomplete>`
    )) as SearchaliciousAutocomplete;
    return el;
  };
  const type = async (el: SearchaliciousAutocomplete, value: string) => {
    const input = el.shadowRoot!.querySelector('input')!;
    input.value = value;
    input.dispatchEvent(new InputEvent('input', {bubbles: true}));
    el.visible = true;
    await el.updateComplete;
    return input;
  };

  test('input is a combobox and options are announced', async () => {
    const el = await autocomplete();
    el.options = [
      {id: 'a', value: 'a', label: 'A', input: 'a'},
      {id: 'b', value: 'b', label: 'B', input: 'a'},
    ];
    const input = await type(el, 'a');
    const list = el.shadowRoot!.querySelector('ul')!;
    assert.equal(input.getAttribute('role'), 'combobox');
    assert.equal(input.getAttribute('aria-expanded'), 'true');
    assert.equal(input.getAttribute('aria-controls'), list.id);
    assert.equal(list.getAttribute('role'), 'listbox');

    input.dispatchEvent(
      new KeyboardEvent('keydown', {key: 'ArrowDown', cancelable: true})
    );
    await el.updateComplete;
    const active = input.getAttribute('aria-activedescendant')!;
    assert.equal(
      el.shadowRoot!.getElementById(active)!.getAttribute('aria-selected'),
      'true'
    );
  });

  test('collapsed when the input is empty', async () => {
    const el = await autocomplete();
    const input = await type(el, '');
    assert.equal(input.getAttribute('aria-expanded'), 'false');
  });

  test('says when there is no result', async () => {
    const el = await autocomplete();
    el.options = [];
    await type(el, 'zzz');
    const item = el.shadowRoot!.querySelector('li')!;
    assert.include(item.textContent, 'No results found');
    assert.equal(item.getAttribute('aria-disabled'), 'true');
  });
});
