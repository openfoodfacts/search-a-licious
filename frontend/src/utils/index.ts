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
