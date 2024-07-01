import {css, LitElement, html, nothing} from 'lit';
import {customElement, property, state} from 'lit/decorators.js';

import {SearchActionMixin} from './mixins/search-action';
import {EventRegistrationMixin} from './event-listener-setup';
import {SearchaliciousEvents} from './utils/enums';

export interface SortParameters {
  sort_by?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  sort_params?: Record<string, any>;
}
/**
 * A component to enable user to choose a search order
 *
 * It must contains searchalicious-sort-options
 * @slot label - rendered on the button
 */
@customElement('searchalicious-sort')
export class SearchaliciousSort extends SearchActionMixin(
  EventRegistrationMixin(LitElement)
) {
  static override styles = css`
    .options {
      list-style: none;
      padding: 0.3em;
      margin: 0;
      background-color: var(--sort-options-background-color, #ffffff);
      position: absolute;
    }
  `;

  /**
   * Wether to relaunch search on sort change
   */
  @property({attribute: 'auto-refresh', type: Boolean})
  autoRefresh = false;

  /**
   * Marker of selected items
   */
  @property({attribute: 'selected-marker'})
  selectedMarker = '▶';

  @state()
  showOptions = false;

  /**
   * return sort options elements
   */
  sortOptions() {
    return Array.from(this.children ?? []).filter((node) =>
      node.nodeName.startsWith('SEARCHALICIOUS-SORT-')
    ) as Array<SearchaliciousSortOption>;
  }

  /**
   * Sort option currently selected
   */
  currentSortOption() {
    return (this.sortOptions().filter((node) => node.selected) ?? [
      undefined,
    ])[0];
  }

  /**
   * Set selected sort option
   */
  setSortOption(option: SearchaliciousSortOption) {
    this.sortOptions().forEach(
      (node) => ((node as SearchaliciousSortOption).selected = node === option)
    );
  }

  getSortOptionId() {
    return this.currentSortOption()?.id;
  }

  /**
   * set selected sort option by using it's id.
   *
   * If optionId is undefined, unselect all
   */
  setSortOptionById(optionId: string | undefined) {
    this.sortOptions().forEach(
      (node) =>
        ((node as SearchaliciousSortOption).selected = node.id === optionId)
    );
  }

  /**
   * Duplicate our selected marker to all children sort options that did not have it yet
   */
  assignSelectedMarker() {
    this.sortOptions().forEach((node) => {
      if (!node.selectedMarker) {
        node.selectedMarker = this.selectedMarker;
      }
    });
  }

  /**
   * Get sort parameters of selected option or return an empty Object
   */
  getSortParameters(): SortParameters | null {
    const option = this.currentSortOption();
    return option ? option.getSortParameters() : null;
  }

  /**
   * sub part to render options when we show them
   */
  _renderOptions() {
    return html`
      <ul class="options" part="options">
        <slot @slotchange=${this.assignSelectedMarker}></slot>
      </ul>
    `;
  }

  override render() {
    return html`
      <button @click=${this._onClick} part="button" role="button">
        <slot name="label">Sort by ▾</slot>
      </button>
      ${this.showOptions ? this._renderOptions() : nothing}
    `;
  }

  /**
   * Show or hide option as we click on the button
   */
  _onClick() {
    this.showOptions = !this.showOptions;
  }

  /**
   * React to a sort option being selected
   * * set currently selected
   * * hide options
   * * eventually launch search
   * @param event
   */
  _handleSelected(event: Event) {
    const option = event.target as SearchaliciousSortOption;
    this.setSortOption(option);
    this.showOptions = false;
    if (this.autoRefresh) {
      this._launchSearch();
    }
  }

  /**
   * Connect option selection event handlers.
   */
  override connectedCallback() {
    super.connectedCallback();
    this.addEventHandler(SearchaliciousEvents.SORT_OPTION_SELECTED, (event) =>
      this._handleSelected(event)
    );
  }
  // disconnect our specific events
  override disconnectedCallback() {
    super.disconnectedCallback();
    this.removeEventHandler(
      SearchaliciousEvents.SORT_OPTION_SELECTED,
      (event) => this._handleSelected(event)
    );
  }
}

/**
 * A sort option component, this is a base class
 *
 * @slot - the content is rendered as is and is considered the content.
 */
export class SearchaliciousSortOption extends LitElement {
  static override styles = css`
    .sort-option {
      display: block;
      margin: 0 0.5rem;
    }
    .sort-option:hover {
      background-color: var(--sort-options-hover-background-color, #dddddd);
    }
    /* making button appear as normal text */
    .sort-option button {
      background-color: transparent;
      border: none;
      color: var(--sort-options-color, #000000);
    }
  `;

  /**
   * If the value is selected.
   * Only one value should be selected at once in a sort component.
   */
  @property({type: Boolean})
  selected = false;

  @property()
  selectedMarker = '';

  /**
   * Eventually gives a default value to id
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  override firstUpdated(changedProperties: Map<any, any>) {
    super.firstUpdated(changedProperties);
    if (!this.id) {
      this.id = this.getDefaultId();
    }
  }

  /**
   * Create a sensible default id for this sort option
   */
  getDefaultId(): string {
    throw new Error('Not implemented');
  }

  /**
   * This is the method that should return the sort paratemetrs
   */
  getSortParameters(): SortParameters {
    throw new Error('Not implemented');
  }

  /**
   * Rendering is a simple li element
   */
  override render() {
    return html`
      <li
        class="sort-option"
        id="${this.id}-li"
        part="sort-option${this.selected ? '-selected' : ''}"
      >
        <button @click=${this._onClick}>
          ${this.selected
            ? html`<span part="selected-marker">${this.selectedMarker}</span>`
            : nothing}
          <slot></slot>
        </button>
      </li>
    `;
  }

  _onClick(event: Event) {
    this.dispatchEvent(
      new CustomEvent(SearchaliciousEvents.SORT_OPTION_SELECTED, {
        bubbles: true,
        composed: true,
      })
    );
    event.preventDefault();
    return false;
  }
}

@customElement('searchalicious-sort-field')
export class SearchaliciousSortField extends SearchaliciousSortOption {
  /**
   * The field name we want to sort on
   */
  @property()
  field = '';

  /** id defaults to field-<field-name> */
  override getDefaultId() {
    return `field-${this.field}`;
  }

  override getSortParameters() {
    return {
      sort_by: this.field,
    };
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'searchalicious-sort': SearchaliciousSort;
    'searchalicious-sort-field': SearchaliciousSortField;
  }
}
