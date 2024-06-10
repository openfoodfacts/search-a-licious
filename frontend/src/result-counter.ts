// lit component to display the result count
import { LitElement, html } from 'lit';
import { customElement, property } from 'lit/decorators.js';

@customElement('result-counter')
export class ResultCounter extends LitElement {
  @property({ type: Number })
  count: number = 0;

  override render() {
    return html`<p>Results: ${this.count}</p>`;
  }
}

declare global {
    interface HTMLElementTagNameMap {
        'result-counter': ResultCounter;
    }
}