/**
 * Event registration mixin to take into account AnimationFrame and avoid race conditions on register / unregister events
 */
//import {LitElement} from 'lit';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Constructor<T = {}> = new (...args: any[]) => T;

export declare class EventRegistrationInterface {
  addEventHandler(
    event: string,
    handler: EventListenerOrEventListenerObject
  ): void;
  removeEventHandler(
    event: string,
    handler: EventListenerOrEventListenerObject
  ): void;
}

export const EventRegistrationMixin = <T extends Constructor<Object>>(
  superClass: T
) => {
  /**
   * The mixin encapsulate the event registration logic
   */
  class EventRegistrationMixinClass extends superClass {
    // this tracks events setups to only add them once to avoid adding / removing them in same animation frame
    _event_setups: {[key: string]: Array<number>} = {};

    addEventHandler(
      event: string,
      handler: EventListenerOrEventListenerObject
    ) {
      this._event_setups[event].push(
        window.requestAnimationFrame(() =>
          this._registrationEventHandlersOnAnimationFrame(event, handler)
        )
      );
    }

    removeEventHandler(
      event: string,
      handler: EventListenerOrEventListenerObject
    ) {
      if (this._event_setups) {
        window.cancelAnimationFrame(this._event_setups[event].pop()!); // cancel one registration
      } else {
        // really remove event
        window.removeEventListener(event, handler);
      }
    }

    _registrationEventHandlersOnAnimationFrame(
      event: string,
      handler: EventListenerOrEventListenerObject,
      options?: boolean | AddEventListenerOptions | undefined
    ) {
      window.addEventListener(event, handler, options);
      this._event_setups[event].pop(); // event registration is done, remove it from queue
    }
  }

  return EventRegistrationMixinClass as Constructor<EventRegistrationInterface> &
    T;
};
