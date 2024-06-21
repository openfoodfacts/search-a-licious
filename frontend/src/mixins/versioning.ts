import {Constructor} from './utils';
import {property} from 'lit/decorators.js';
import {LitElement} from 'lit';

export interface VersioningMixinInterface {
  version: number;
  incrementVersion(): number;
  isLatestVersion(version: number): boolean;
}
export const VersioningMixin = <T extends Constructor<LitElement>>(
  superClass: T
) => {
  /**
   * The mixin encapsulate the versioning logic
   * It allows to avoid updating the data with older responses
   */
  class VersioningMixinClass extends superClass {
    /**
     * The version of the object
     */
    @property({attribute: false})
    version = 0;

    /**
     * Increment the version of the object
     */
    incrementVersion() {
      this.version++;
      return this.version;
    }

    /**
     * Check if the version is the latest
     */
    isLatestVersion(version: number) {
      return version === this.version;
    }
  }

  return VersioningMixinClass as Constructor<VersioningMixinInterface> & T;
};
