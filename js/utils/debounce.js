export const debounce = (func, wait, immediate = false) => {
  let timeout;
  return function (...args) {
    const callNow = immediate && !timeout;
    clearTimeout(timeout);
    timeout = setTimeout(() => {
      timeout = null;
      if (!immediate) func.apply(this, args);
    }, wait);
    if (callNow) func.apply(this, args);
  };
};
