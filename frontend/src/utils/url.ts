/**
 * Set the URL parameters history
 * @param url
 * @param params
 */
export const setURLHistory = (
  url: string,
  params: Record<string, string | undefined>
): string => {
  const urlObj = new URL(url);
  for (const key in params) {
    if (params[key] === undefined) {
      urlObj.searchParams.delete(key);
      continue;
    }
    urlObj.searchParams.set(key, params[key]!);
  }
  const newUrl = urlObj.toString();
  window.history.pushState({}, '', newUrl);
  return newUrl;
};

/**
 * Set the current URL parameters history
 * @param params
 */

export const setCurrentURLHistory = (
  params: Record<string, string | undefined>
): string => {
  const url = window.location.href;
  return setURLHistory(url, params);
};

/**
 * Remove parenthesis from a string
 * for example: "(test OR test2)" => "test OR test2"
 */
export const removeParenthesis = (value: string): string => {
  if (value.startsWith('(') && value.endsWith(')')) {
    return value.slice(1, -1);
  } else {
    return value;
  }
};

/**
 * Add a prefix to a string
 * for example: addParamPrefix('test', 'off') => 'off_test'
 */
export const addParamPrefix = (value: string, prefix: string): string => {
  return `${prefix}_${value}`;
};

/**
 * Add a prefix to all keys of an object
 * @param obj
 * @param prefix
 */
export const addParamPrefixes = (
  obj: Record<string, unknown>,
  prefix: string
): Record<string, unknown> => {
  const newObj: Record<string, unknown> = {};
  for (const key in obj) {
    newObj[addParamPrefix(key, prefix)] = obj[key];
  }
  return newObj;
};

/**
 * Remove a prefix from a string
 * for example: removeParamPrefix('off_test', 'off') => 'test'
 */
export const removeParamPrefix = (value: string, prefix: string): string => {
  return value.replace(`${prefix}_`, '');
};

/**
 * Remove a prefix from all keys of an object
 * @param obj
 * @param prefix
 */
export const removeParamPrefixes = (
  obj: Record<string, string>,
  prefix: string
): Record<string, string> => {
  const newObj: Record<string, string> = {};
  for (const key in obj) {
    newObj[removeParamPrefix(key, prefix)] = obj[key];
  }
  return newObj;
};
