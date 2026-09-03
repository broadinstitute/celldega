/* global require */

// Shared gene name/description presentation used by the Clustergram row
// tooltip + info box, the Landscape transcript tooltip, and Enrich.

const load_gene_info = (cache) => {
  const fs = require('fs');
  const path = require('path');

  const source = fs
    .readFileSync(path.join(__dirname, '../ui/gene_info.js'), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');

  // Stand-in for the module-level UniProt cache in uniprot_api.js.
  const shims = `
    const get_uniprot_info = (gene) => cache[gene];
    const has_uniprot_info = (gene) => Boolean(gene) && gene in cache;
    const request_uniprot_info = (gene) => {
      requested.push(gene);
      return Promise.resolve(cache[gene]);
    };
  `;
  const code = `${shims}\n${source}\nmodule.exports = { escape_html, is_gene_axis, gene_info_tooltip_html, refresh_gene_tooltip_async, contain_scroll, make_gene_info_box, make_gene_hover_tooltip, requested };`;
  const module = { exports: {} };
  const requested = [];
  new Function('module', 'exports', 'cache', 'requested', code)(
    module,
    module.exports,
    cache,
    requested
  );
  return module.exports;
};

describe('gene info tooltip text', () => {
  test('shows a placeholder until the lookup lands, then name + description', () => {
    const cache = {};
    let api = load_gene_info(cache);

    expect(api.gene_info_tooltip_html('BRD4')).toContain('Looking up UniProt');

    cache.BRD4 = {
      name: 'Bromodomain-containing protein 4',
      description: 'Chromatin reader.',
    };
    api = load_gene_info(cache);

    const html = api.gene_info_tooltip_html('BRD4');
    expect(html).toContain('Bromodomain-containing protein 4');
    expect(html).toContain('Chromatin reader.');
    expect(html).not.toContain('Looking up');
  });

  test('renders nothing extra when UniProt had no usable entry', () => {
    const api = load_gene_info({
      MOCK1: { name: '', description: 'Unable to obtain UniProt description.' },
    });

    expect(api.gene_info_tooltip_html('MOCK1')).toBe('');
    expect(api.gene_info_tooltip_html('')).toBe('');
  });

  test('escapes gene descriptions (they are injected as HTML)', () => {
    const api = load_gene_info({
      EVIL: { name: '<img src=x onerror=alert(1)>', description: 'a & b' },
    });

    const html = api.gene_info_tooltip_html('EVIL');
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('<img');
    expect(html).toContain('a &amp; b');
  });

  test('is_gene_axis reads either entity shape', () => {
    const api = load_gene_info({});

    expect(api.is_gene_axis({ row_entity: { entity: 'gene' } }, 'row')).toBe(
      true
    );
    expect(api.is_gene_axis({ row_entity: 'Gene' }, 'row')).toBe(true);
    expect(api.is_gene_axis({ row_entity: { entity: 'cell' } }, 'row')).toBe(
      false
    );
    expect(api.is_gene_axis({}, 'row')).toBe(false);
  });
});

describe('gene info box (stateful: selection only)', () => {
  test('shows the selected gene and clears', async () => {
    const cache = {
      AAA: { name: 'Alpha', description: 'first' },
      BBB: { name: 'Beta', description: 'second' },
    };
    const api = load_gene_info(cache);
    const box = api.make_gene_info_box();

    box.show('AAA');
    await Promise.resolve();
    expect(box.element.innerHTML).toContain('Alpha');
    expect(box.element.innerHTML).toContain('first');

    box.show('BBB');
    await Promise.resolve();
    expect(box.element.innerHTML).toContain('Beta');

    box.clear();
    await Promise.resolve();
    expect(box.element.innerHTML).toBe('');
  });

  test('a stale in-flight lookup never overwrites a newer selection', async () => {
    const cache = { AAA: { name: 'Alpha', description: 'first' } };
    const api = load_gene_info(cache);
    const box = api.make_gene_info_box();

    // MISSING is not cached, so its render awaits; BBB then supersedes it.
    cache.BBB = { name: 'Beta', description: 'second' };
    box.show('MISSING');
    box.show('BBB');

    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();

    expect(box.element.innerHTML).toContain('Beta');
    expect(box.element.innerHTML).not.toContain('loading');
  });

  test('exposes no hover API — transient info belongs in the tooltip', () => {
    const api = load_gene_info({});
    const box = api.make_gene_info_box();

    expect(box.preview).toBeUndefined();
    expect(box.clear_preview).toBeUndefined();
  });
});

describe('gene hover tooltip (transient)', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test('shows a gene at the pointer after the dwell, and hides on leave', async () => {
    const api = load_gene_info({
      AAA: { name: 'Alpha', description: 'first' },
    });
    const tooltip = api.make_gene_hover_tooltip();
    const element = document.querySelector('.gene_hover_tooltip');

    expect(element.style.display).toBe('none');

    tooltip.show('AAA', { clientX: 100, clientY: 50 });
    // Nothing shown until the pointer has rested.
    expect(element.style.display).toBe('none');

    jest.advanceTimersByTime(200);
    await Promise.resolve();

    expect(element.style.display).toBe('block');
    expect(element.innerHTML).toContain('Alpha');
    expect(element.style.left).toBe('114px');
    expect(element.style.top).toBe('64px');
    // Same dark box deck.gl uses for the Clustergram/Landscape tooltips.
    expect(element.style.background).toBe('rgb(41, 50, 60)');
    expect(element.style.color).toBe('white');
    expect(element.innerHTML).toContain('#7fb0ff');

    tooltip.hide();
    expect(element.style.display).toBe('none');

    tooltip.destroy();
  });

  test('sweeping across genes issues no lookups', () => {
    const api = load_gene_info({});
    const tooltip = api.make_gene_hover_tooltip();

    // Pointer passes over three genes without resting on any of them.
    ['AAA', 'BBB', 'CCC'].forEach((gene) => {
      tooltip.show(gene, { clientX: 0, clientY: 0 });
      jest.advanceTimersByTime(40);
    });
    tooltip.hide();
    jest.advanceTimersByTime(500);

    expect(api.requested).toEqual([]);
    tooltip.destroy();
  });

  test('appends extra content (e.g. enrichment stats) below the description', () => {
    const api = load_gene_info({
      AAA: { name: 'Alpha', description: 'first' },
    });
    const tooltip = api.make_gene_hover_tooltip();
    const element = document.querySelector('.gene_hover_tooltip');

    tooltip.show('AAA', { clientX: 0, clientY: 0 }, '<br>In 2 of 10 terms');
    jest.advanceTimersByTime(200);

    expect(element.innerHTML).toContain('In 2 of 10 terms');
    tooltip.destroy();
  });

  test('show_html renders arbitrary content (enrichment term stats)', () => {
    const api = load_gene_info({});
    const tooltip = api.make_gene_hover_tooltip();
    const element = document.querySelector('.gene_hover_tooltip');

    tooltip.show_html('<b>Term</b><br>p-value: 1.0e-5', {
      clientX: 10,
      clientY: 20,
    });
    jest.advanceTimersByTime(200);

    expect(element.style.display).toBe('block');
    expect(element.innerHTML).toContain('p-value: 1.0e-5');
    tooltip.destroy();
  });

  test('a late lookup only lands if the pointer is still on that gene', async () => {
    const cache = {};
    const api = load_gene_info(cache);
    const tooltip = api.make_gene_hover_tooltip();
    const element = document.querySelector('.gene_hover_tooltip');

    tooltip.show('SLOW', { clientX: 0, clientY: 0 });
    jest.advanceTimersByTime(200);
    expect(element.innerHTML).toContain('loading');

    // Pointer leaves before the fetch resolves.
    cache.SLOW = { name: 'Slow', description: 'late' };
    tooltip.hide();
    await Promise.resolve();
    await Promise.resolve();

    expect(element.style.display).toBe('none');
    tooltip.destroy();
  });
});

describe('deck.gl tooltip lookups are dwell-gated', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  const make_root = () => {
    const root = document.createElement('div');
    const tooltip = document.createElement('div');
    tooltip.className = 'deck-tooltip';
    tooltip.style.display = 'block';
    root.appendChild(tooltip);
    return { root, tooltip };
  };

  test('a fast sweep down row labels issues no lookups', () => {
    const api = load_gene_info({});
    const { root } = make_root();

    ['AAA', 'BBB', 'CCC'].forEach((gene) => {
      api.refresh_gene_tooltip_async(root, gene, () => gene);
      jest.advanceTimersByTime(40);
    });

    expect(api.requested).toEqual([]);
  });

  test('resting on a gene patches the live tooltip', async () => {
    const cache = { AAA: { name: 'Alpha', description: 'first' } };
    const api = load_gene_info(cache);
    const { root, tooltip } = make_root();

    // Not yet cached from this module's perspective: force the async path.
    delete cache.AAA;
    api.refresh_gene_tooltip_async(root, 'AAA', () => 'patched');
    cache.AAA = { name: 'Alpha', description: 'first' };

    jest.advanceTimersByTime(200);
    await Promise.resolve();
    await Promise.resolve();

    expect(api.requested).toEqual(['AAA']);
    expect(tooltip.innerHTML).toBe('patched');
  });
});

describe('scroll containment', () => {
  // jsdom does no layout, so overflow has to be declared explicitly.
  const make_scrollable = (element, { content = 500, visible = 100 } = {}) => {
    Object.defineProperty(element, 'scrollHeight', { value: content });
    Object.defineProperty(element, 'clientHeight', { value: visible });
    return element;
  };

  const wheel = (element, init = { deltaY: 40 }) => {
    const event = new window.WheelEvent('wheel', {
      bubbles: true,
      cancelable: true,
      ...init,
    });
    const stop = jest.spyOn(event, 'stopPropagation');
    element.dispatchEvent(event);
    return { event, stop };
  };

  test('wheel gestures scroll the element without reaching the page', () => {
    const api = load_gene_info({});
    const element = make_scrollable(document.createElement('div'));
    document.body.appendChild(element);
    api.contain_scroll(element);

    expect(element.style.overscrollBehavior).toBe('contain');

    const { event, stop } = wheel(element);

    // Page scroll cancelled, widget handlers never see it, box scrolled.
    expect(event.defaultPrevented).toBe(true);
    expect(stop).toHaveBeenCalled();
    expect(element.scrollTop).toBe(40);
  });

  test('scrolls the overflow container when attached to inner content', () => {
    // The Enrich paragraph view's shape: a non-scrolling content div inside a
    // scrolling holder. Cancelling the native scroll without redirecting it
    // here is what broke that panel's scrolling entirely.
    const api = load_gene_info({});
    const holder = make_scrollable(document.createElement('div'));
    const content = document.createElement('div');
    holder.appendChild(content);
    document.body.appendChild(holder);

    api.contain_scroll(content);
    wheel(content);

    expect(holder.scrollTop).toBe(40);
  });

  test('never scrolls the page when nothing in the widget overflows', () => {
    const api = load_gene_info({});
    const element = document.createElement('div');
    document.body.appendChild(element);
    api.contain_scroll(element);

    const { event } = wheel(element);

    expect(event.defaultPrevented).toBe(true);
    expect(element.scrollTop).toBe(0);
  });

  test('converts line-mode deltas (Firefox) to pixels', () => {
    const api = load_gene_info({});
    const element = make_scrollable(document.createElement('div'));
    document.body.appendChild(element);
    api.contain_scroll(element);

    wheel(element, { deltaY: 3, deltaMode: 1 });

    expect(element.scrollTop).toBe(48);
  });
});
