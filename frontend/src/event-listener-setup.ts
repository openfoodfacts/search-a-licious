/**
 * Event registration mixin to take into account AnimationFrame and avoid race conditions on register / unregister events
 */
//import {LitElement} from 'lit';
import {Constructor} from './mixins/utils';
import {EventRegistrationInterface} from './interfaces/events-interfaces';

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
      this._event_setups[event] ||= [];
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
      if (this._event_setups[event]) {
        window.cancelAnimationFrame(this._event_setups[event].pop()!); // cancel one registration
      } else {
        // really remove event
        window.removeEventListener(event, handler);
      }
    }

    // method called on next animation frame to actually add the event listener,
    // if not eventually canceled by a removeEventHandler call
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
