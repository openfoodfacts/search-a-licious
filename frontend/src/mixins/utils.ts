/**
 * This mixin represents a mixin type
 *
 * We need it for every mixin we declare.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Constructor<T = {}> = new (...args: any[]) => T;
