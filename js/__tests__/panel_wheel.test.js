/* global require */

// Vertical wheel gestures over a control panel must not scroll the page,
// while scrollable boxes inside it (bar plots, gene info) still scroll.
const fs = require('fs');
const path = require('path');

describe('block_page_scroll_in_panel', () => {
  let block_page_scroll_in_panel;

  beforeAll(() => {
    const source = fs.readFileSync(
      path.join(__dirname, '../ui/ui_containers.js'),
      'utf8'
    );
    const start = source.indexOf('const can_scroll_vertically');
    const end = source.indexOf('export const make_ui_container');
    const snippet = source
      .slice(start, end)
      .replace(/^export const /gm, 'const ');
    block_page_scroll_in_panel = new Function(
      `${snippet}; return block_page_scroll_in_panel;`
    )();
  });

  const wheel = (panel, target, { deltaX = 0, deltaY = 0 }) => {
    const event = new WheelEvent('wheel', {
      deltaX,
      deltaY,
      bubbles: true,
      cancelable: true,
    });
    panel.addEventListener('wheel', block_page_scroll_in_panel, {
      passive: false,
    });
    target.dispatchEvent(event);
    panel.removeEventListener('wheel', block_page_scroll_in_panel);
    return event.defaultPrevented;
  };

  const make_scroll_box = ({ scrollTop, scrollHeight, clientHeight }) => {
    const box = document.createElement('div');
    box.style.overflowY = 'auto';
    Object.defineProperty(box, 'scrollHeight', { value: scrollHeight });
    Object.defineProperty(box, 'clientHeight', { value: clientHeight });
    box.scrollTop = scrollTop;
    return box;
  };

  test('absorbs vertical wheel over plain panel content', () => {
    const panel = document.createElement('div');
    const label = document.createElement('span');
    panel.appendChild(label);
    expect(wheel(panel, label, { deltaY: 40 })).toBe(true);
  });

  test('lets a scrollable box scroll while it has room', () => {
    const panel = document.createElement('div');
    const box = make_scroll_box({
      scrollTop: 0,
      scrollHeight: 300,
      clientHeight: 72,
    });
    const bar = document.createElement('div');
    box.appendChild(bar);
    panel.appendChild(box);

    expect(wheel(panel, bar, { deltaY: 40 })).toBe(false); // room below
    expect(wheel(panel, bar, { deltaY: -40 })).toBe(true); // already at top
  });

  test('leaves horizontal gestures alone', () => {
    const panel = document.createElement('div');
    expect(wheel(panel, panel, { deltaX: 40, deltaY: 5 })).toBe(false);
  });
});
