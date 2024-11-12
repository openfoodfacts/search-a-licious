export interface EventRegistrationInterface {
  /**
   * Calls window.addEventListener if not remove before next AnimationFrame
   * @param event - event name
   * @param handler - function handling event. Beware of using () => this.method to have method bind to this.
   */
  addEventHandler(
    event: string,
    handler: EventListenerOrEventListenerObject
  ): void;
  /**
   * Removes window.removeEventListener but only if really needed
   * @param event - event name
   * @param handler - function handling event.
   */
  removeEventHandler(
    event: string,
    handler: EventListenerOrEventListenerObject
  ): void;
}
