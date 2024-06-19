/**
 * Filter an object by keys
 * @param obj
 * @param keys
 * @return a new object with keys matching filter and corresponding values.
 */
export const filterObjectByKeys = <T>(obj: T, keys: string[]): Partial<T> => {
  const newObj: Partial<T> = {};
  for (const key of keys) {
    const typedKey = key as keyof T;
    if (obj[typedKey]) {
      newObj[typedKey] = obj[typedKey];
    }
  }
  return newObj;
};

/**
 * Check if a value is null or undefined
 * @param value
 */
export const isNullOrUndefined = (
  value: unknown
): value is null | undefined => {
  return value === null || value === undefined;
};
