import {css, html, LitElement} from 'lit';
import {customElement, property} from 'lit/decorators.js';
import {SuggestionSelectionOption} from './interfaces/suggestion-interfaces';

/**
 * This component represent a suggestion to the user as he types his search.
 *
 * It's an internal component meant to be used by the search-bar.
 */
@customElement('searchalicious-suggestion-entry')
export class SearchaliciousSuggestionEntry extends LitElement {
  /**
   * The styles for the suggestion entry.
   * .suggestion-entry: The container for the suggestion entry, it contains the image and the text.
   * .suggestion-entry-img-wrapper: The container for the image. It takes a fixed size by default is 2rem.
   * .suggestion-entry-text-wrapper: The container for the text. It takes the remaining space.
   * .suggestion-entry-img-wrapper > *: The image itself. It takes the full size of the container.
   * .suggestion-entry-text: The text of the suggestion.
   */
  static override styles = css`
    .suggestion-entry {
      display: flex;
      align-items: center;
      padding: 0.5rem 1rem;
      box-sizing: border-box;
      overflow: hidden;
      max-width: 100%;

      --img-size: var(--searchalicious-suggestion-entry-img-size, 2rem);
    }

    .suggestion-entry .suggestion-entry-text-wrapper {
      --margin-left: 1rem;
      margin-left: var(--margin-left);
      width: calc(100% - var(--img-size) - var(--margin-left));
    }

    .suggestion-entry-text {
      font-weight: bold;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
      overflow: hidden;
    }
  `;

  @property({type: Object, attribute: 'term'})
  term?: SuggestionSelectionOption;

  /**
   * We display the taxonomy term and corresponding filter name
   */
  override render() {
    return html`
      <div class="suggestion-entry">
        <div class="suggestion-entry-text-wrapper">
          <div class="suggestion-entry-text">${this.term?.label}</div>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-suggestion-entry': SearchaliciousSuggestionEntry;
  }
}
