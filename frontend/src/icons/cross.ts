import {LitElement, html, css} from 'lit';
import {customElement} from 'lit/decorators.js';

/**
 * A custom element that represents a cross icon.
 * You can modify this variable to customize the icon style :
 * --icon-width by default 0.8rem
 * --icon-stroke-color by default black
 */
@customElement('searchalicious-icon-cross')
export class SearchaliciousIconCross extends LitElement {
  static override styles = css`
    svg {
      width: var(--icon-width, 0.8rem);
    }
    svg line {
      stroke: var(--icon-stroke-color, black);
    }
  `;
  override render() {
    return html`
      <svg
        part="icon-cross"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid meet"
        xmlns="http://www.w3.org/2000/svg"
      >
        <line
          x1="10"
          y1="10"
          x2="90"
          y2="90"
          style="stroke:black;stroke-width:10"
        />
        <line
          x1="90"
          y1="10"
          x2="10"
          y2="90"
          style="stroke:black;stroke-width:10"
        />
      </svg>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-icon-cross': SearchaliciousIconCross;
  }
}
