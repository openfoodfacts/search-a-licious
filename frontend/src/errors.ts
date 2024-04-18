/**
 * An error thrown if we don't have a template in results component
 */
export class MissingResultTemplateError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'MissingResultTemplateError';
  }
}

/**
 * An error thrown if we have multiple templates in results component
 */
export class MultipleResultTemplateError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'MultipleResultTemplateError';
  }
}
