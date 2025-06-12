function Observable(initialValue) {

  let value = initialValue;
  const subscribers = new Set()

  return {
    get: () => value,
    getDefault: () => initialValue,
    set: newValue => {
      if (value !== newValue) {
        value = newValue;
        subscribers.forEach(fn => fn(value));
      }
    },
    subscribe: fn => {
      subscribers.add(fn);
      fn(value); // Call immediately with current value
      return () => subscribers.delete(fn); // Un_catsubscribe function
    }
  }

}

export const obs_store = {
  cat: Observable("cluster"),
  selected_cats: Observable([]),
}