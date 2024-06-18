import {css, html, LitElement} from 'lit';
import {customElement, property} from 'lit/decorators.js';

@customElement('searchalicious-term-line')
export class SearchaliciousTermLine extends LitElement {
  static override styles = css`
    .term-line {
      display: flex;
      align-items: center;
      padding: 0.5rem 1rem;
      box-sizing: border-box;
      overflow: hidden;
      max-width: 100%;

      --img-size: 2rem;
    }

    .term-line-img-wrapper {
      width: 2rem;
      height: 2rem;
      overflow: hidden;
    }

    .term-line-text-wrapper {
      --margin-left: 1rem;
      margin-left: var(--margin-left);
      width: calc(100% - var(--img-size) - var(--margin-left));
    }

    .term-line-img-wrapper > * {
      width: 100%;
      height: 100%;
      object-fit: cover;
      border-radius: 50%;
      background-color: var(--img-background-color, #d9d9d9);
    }

    .term-line-text {
      font-weight: bold;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
      overflow: hidden;
    }
  `;

  @property({type: Object, attribute: 'term'})
  term?: {
    imageUrl?: string;
    id: string;
    text: string;
    taxonomy_name: string;
  };

  override render() {
    return html`
      <div class="term-line">
        <div class="term-line-img-wrapper">
          ${this.term?.imageUrl
            ? html`<img src=${this.term?.imageUrl} />`
            : html`<div></div>`}
        </div>
        <div class="term-line-text-wrapper">
          <div class="term-line-text">${this.term?.text}</div>
          <div>${this.term?.taxonomy_name}</div>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-term-line': SearchaliciousTermLine;
  }
}
