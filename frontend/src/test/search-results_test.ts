// import {SearchaliciousResults} from '../search-results';
// import {SearchaliciousEvents} from '../utils/enums';
// import {SearchResultDetail} from '../events';
//
// import {fixture, assert, expect} from '@open-wc/testing';
// import {html} from 'lit/static-html.js';
// import {
//   MissingResultTemplateError,
//   MultipleResultTemplateError,
// } from '../errors';
// import {DEFAULT_SEARCH_NAME} from '../utils/constants';
//
// suite('searchalicious-results', () => {
//   // helper to simulate a search result
//   const emitSearchResult = (
//     el: SearchaliciousResults,
//     results: Array<Record<string, unknown>>
//   ) => {
//     const detail: SearchResultDetail = {
//       searchName: DEFAULT_SEARCH_NAME,
//       results: results,
//       count: 3,
//       pageCount: 1,
//       currentPage: 1,
//       pageSize: 10,
//       facets: {},
//       charts: {},
//     };
//     el._handleResults(
//       new CustomEvent(SearchaliciousEvents.NEW_RESULT, {
//         bubbles: true,
//         composed: true,
//         detail: detail,
//       })
//     );
//   };
//
//   test('is defined', () => {
//     const el = document.createElement('searchalicious-results');
//     assert.instanceOf(el, SearchaliciousResults);
//   });
//
//   test('renders with default values', async () => {
//     const el = (await fixture(html`<searchalicious-results>
//       <div slot="result">
//         <li id="result-\${index}" part="li">
//           \${result.id} <b>\${result.data}</b>
//         </li>
//       </div>
//     </searchalicious-results>`)) as SearchaliciousResults;
//     // empty at first
//     assert.equal(el.searchLaunched, false);
//     assert.deepEqual(el.results, []);
//     assert.shadowDom.equal(el, '<slot name="before-search"></slot>');
//     // emit search result
//     const searchResults = [
//       {id: 1, data: 'a'},
//       {id: 2, data: 'b'},
//       {id: 3, data: 'c'},
//     ];
//     emitSearchResult(el, searchResults);
//     await el.updateComplete;
//     assert.equal(el.searchLaunched, true);
//     assert.deepEqual(el.results, searchResults);
//     assert.shadowDom.equal(
//       el,
//       `
//       <ul part="results">
//         <li id="result-0" part="li">1 <b>a</b></li>
//         <li id="result-1" part="li">2 <b>b</b></li>
//         <li id="result-2" part="li">3 <b>c</b></li>
//       </ul>`
//     );
//     // emit an empty search result
//     emitSearchResult(el, []);
//     await el.updateComplete;
//     assert.equal(el.searchLaunched, true);
//     assert.deepEqual(el.results, []);
//     assert.shadowDom.equal(
//       el,
//       '<slot name="no-results"><div> No results found </div></slot>'
//     );
//   });
//   test('No result slot raises', () => {
//     const el = document.createElement('searchalicious-results');
//     expect(() => el._getTemplate('result')).to.throw(
//       MissingResultTemplateError
//     );
//   });
//   test('Two result slot raises', () => {
//     const el = document.createElement('searchalicious-results');
//     el.append(document.createElement('div'), document.createElement('p'));
//     el.children[0].setAttribute('slot', 'result');
//     el.children[1].setAttribute('slot', 'result');
//     expect(() => el._getTemplate('result')).to.throw(
//       MultipleResultTemplateError
//     );
//   });
//
//   /* DON'T KNOW WHY NONE OF THIS DO NOT WORK !
//   test('No result slot raises', async () => {
//     // this does not work and I don't know why :-(
//       const tpl = html`<searchalicious-results></searchalicious-results>`;
//       fixture(tpl)
//       .then(() => assert.fail("Expected MissingResultTemplateError to be thrown"))
//       .catch((error) => assert.fail("YYY Expected MissingResultTemplateError to be thrown")); //expect(error).to.be.instanceOf(MissingResultTemplateError)});
//       //expect(() => fixture(html`<searchalicious-results></searchalicious-results>`)).to.throw();
//     //expect(() => fixtureSync(html`<searchalicious-results></searchalicious-results>`)).to.throw(MissingResultTemplateError);
//     //await expect(async () => await fixture(html`<searchalicious-results></searchalicious-results>`)).to.eventually.be.rejected(MissingResultTemplateError);
//     // try {
//     //   await fixture(html`<searchalicious-results></searchalicious-results>`);
//     //   assert.fail("Expected MissingResultTemplateError to be thrown");
//     // } catch (error) {
//     //   expect(error).to.be.instanceOf(MissingResultTemplateError);
//     // }
//   });
//   */
//
//   test('render with specific before search', async () => {
//     const el = (await fixture(html`<searchalicious-results>
//       <div slot="result"></div>
//       <p slot="before-search">Try to search <span>something</span></p>
//     </searchalicious-results>`)) as SearchaliciousResults;
//     // empty at first
//     assert.equal(el.searchLaunched, false);
//     assert.deepEqual(el.results, []);
//     assert.shadowDom.equal(el, `<slot name="before-search"></slot>`);
//   });
//
//   test('render with specific no results', async () => {
//     const el = (await fixture(html`<searchalicious-results>
//       <div slot="result"></div>
//       <p slot="no-results">Try <span>again !</span></p>
//     </searchalicious-results>`)) as SearchaliciousResults;
//     // emit an empty search result
//     emitSearchResult(el, []);
//     await el.updateComplete;
//     assert.equal(el.searchLaunched, true);
//     assert.deepEqual(el.results, []);
//     assert.shadowDom.equal(
//       el,
//       `<slot name="no-results"><div> No results found </div></slot>`
//     );
//   });
// });
