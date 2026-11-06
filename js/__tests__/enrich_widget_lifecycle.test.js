/* global require */

describe('Enrich widget lifecycle', () => {
  let render_enrich;
  let tooltip;
  let unsubscribeMocks;
  let postGeneList;
  let fetchEnrichment;

  beforeEach(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(path.join(__dirname, '../widgets/enrich_widget.js'), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    unsubscribeMocks = [];
    const Observable = (initialValue) => {
      let value = initialValue;
      const subscribers = new Set();
      return {
        get: () => value,
        set: (next) => {
          if (value === next) return;
          value = next;
          subscribers.forEach((subscriber) => subscriber(value));
        },
        subscribe: (subscriber, options = { immediate: true }) => {
          subscribers.add(subscriber);
          if (options.immediate) subscriber(value);
          const unsubscribe = jest.fn(() => subscribers.delete(subscriber));
          unsubscribeMocks.push(unsubscribe);
          return unsubscribe;
        },
      };
    };

    const create_enrich_store = () => ({
      available_libs: Observable([]),
      selected_lib: Observable('CellMarker_2024'),
      term_genes: Observable([]),
      gene_of_interest: Observable(''),
      selected_term: Observable('Select Term'),
    });
    tooltip = {
      show: jest.fn(),
      show_html: jest.fn(),
      move: jest.fn(),
      hide: jest.fn(),
      destroy: jest.fn(),
    };
    postGeneList = jest.fn();
    fetchEnrichment = jest.fn();

    const factory = new Function(
      'd3',
      'postGeneList',
      'fetchEnrichment',
      'create_enrich_store',
      'handleAsyncError',
      'contain_scroll',
      'escape_html',
      'make_gene_hover_tooltip',
      'make_logo_button',
      'updateParagraphColors',
      'updateGeneInfo',
      `${source}; return render_enrich;`
    );

    render_enrich = factory(
      {},
      postGeneList,
      fetchEnrichment,
      create_enrich_store,
      jest.fn(),
      jest.fn(),
      (value) => String(value),
      () => tooltip,
      () => document.createElement('button'),
      jest.fn(),
      jest.fn()
    );
  });

  const makeModel = (overrides = {}) => {
    const values = {
      available_libs: [],
      inst_lib: 'CellMarker_2024',
      gene_list: [],
      source_label: '',
      num_terms: 10,
      background_list: [],
      focused_gene: '',
      term_genes: ['stale-gene'],
      selected_term: 'Stale term',
      width: 350,
      height: 500,
      ...overrides,
    };
    const listeners = new Map();

    const model = {
      get: jest.fn((name) => values[name]),
      set: jest.fn((name, value) => {
        if (values[name] === value) return;
        values[name] = value;
        (listeners.get(`change:${name}`) || []).forEach((listener) =>
          listener()
        );
      }),
      save_changes: jest.fn(),
      on: jest.fn((event, listener) => {
        listeners.set(event, [...(listeners.get(event) || []), listener]);
      }),
      off: jest.fn((event, listener) => {
        listeners.set(
          event,
          (listeners.get(event) || []).filter((item) => item !== listener)
        );
      }),
    };

    return { model, values, listeners };
  };

  test('clears stale terms and releases external listeners on finalize', async () => {
    const { model, values, listeners } = makeModel();
    const el = document.createElement('div');

    const cleanup = await render_enrich({ model, el });

    expect(values.term_genes).toEqual([]);
    expect(values.selected_term).toBe('Select Term');
    expect(typeof cleanup).toBe('function');
    expect(el.childElementCount).toBe(1);

    cleanup();

    expect(tooltip.destroy).toHaveBeenCalledTimes(1);
    expect(model.off).toHaveBeenCalledTimes(9);
    expect([...listeners.values()].every((items) => items.length === 0)).toBe(
      true
    );
    expect(unsubscribeMocks).toHaveLength(4);
    unsubscribeMocks.forEach((unsubscribe) =>
      expect(unsubscribe).toHaveBeenCalledTimes(1)
    );
    expect(el.childElementCount).toBe(0);
  });

  test('cleanup stops an in-flight submission before enrichment starts', async () => {
    let resolveSubmission;
    postGeneList.mockReturnValue(
      new Promise((resolve) => {
        resolveSubmission = resolve;
      })
    );
    const { model } = makeModel({
      gene_list: ['g0'],
      term_genes: [],
      selected_term: 'Select Term',
    });

    const cleanup = await render_enrich({
      model,
      el: document.createElement('div'),
    });
    expect(postGeneList).toHaveBeenCalledTimes(1);

    cleanup();
    resolveSubmission({ userListId: 123, shortId: 'abc' });
    await Promise.resolve();
    await Promise.resolve();

    expect(fetchEnrichment).not.toHaveBeenCalled();
  });
});
