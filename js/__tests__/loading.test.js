/* global require */

// The loading placeholder shown while a Landscape / CellCloud fetches its data.
describe('show_loading', () => {
  let show_loading;

  beforeEach(() => {
    const fs = require('fs');
    const path = require('path');
    const read = (file) =>
      fs
        .readFileSync(path.join(__dirname, file), 'utf8')
        .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
        .replace(/^export const /gm, 'const ');
    show_loading = new Function(
      `${read('../ui/logo.js')}\n${read('../ui/loading.js')}\nreturn show_loading;`
    )();
  });

  test('shows the awning mark and "Loading…" until removed', () => {
    const el = document.createElement('div');
    el.appendChild(document.createElement('span'));
    const remove = show_loading(el, { height: 600 });

    const box = el.firstChild;
    expect(box.className).toBe('celldega-loading');
    expect(box.style.height).toBe('600px');
    expect(box.querySelector('img').src).toMatch(/^data:image\/png;base64,/);
    expect(box.textContent).toBe('Loading…');
    expect(document.getElementById('celldega-loading-style')).not.toBeNull();

    remove();
    expect(el.querySelector('.celldega-loading')).toBeNull();
    expect(el.children).toHaveLength(1); // the widget's own content is untouched
  });

  test('keeps a minimum height and adds its style only once', () => {
    const el = document.createElement('div');
    show_loading(el, { height: 0 })();
    show_loading(el, { height: 0 });
    expect(el.firstChild.style.height).toBe('120px');
    expect(document.querySelectorAll('#celldega-loading-style')).toHaveLength(
      1
    );
  });
  test('with a delay, a quick render never shows it', () => {
    jest.useFakeTimers();
    try {
      const el = document.createElement('div');
      const remove = show_loading(el, { delay: 150 });
      expect(el.querySelector('.celldega-loading')).toBeNull();
      remove();
      jest.advanceTimersByTime(500);
      expect(el.querySelector('.celldega-loading')).toBeNull();

      const slow = show_loading(el, { delay: 150 });
      jest.advanceTimersByTime(200);
      expect(el.querySelector('.celldega-loading')).not.toBeNull();
      slow();
      expect(el.querySelector('.celldega-loading')).toBeNull();
    } finally {
      jest.useRealTimers();
    }
  });
});
