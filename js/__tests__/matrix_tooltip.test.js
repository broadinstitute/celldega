/* global require */

describe('matrix tooltip positioning', () => {
  let get_tooltip;
  let hide_tooltip;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/matrix/matrix_tooltip.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    // Real implementations from ui/gene_info.js (kept in sync by the
    // gene-info tests); the tooltip only needs their contract here.
    const shims = `
      const escape_html = (value) =>
        String(value ?? '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');
      const is_gene_axis = (viz_state, axis = 'row') => {
        const raw = viz_state?.[axis + '_entity'];
        const entity = raw?.entity ?? raw;
        return String(entity ?? '').toLowerCase() === 'gene';
      };
      const gene_info_tooltip_html = (gene) =>
        gene ? '<br><i>Looking up UniProt…</i>' : '';
      const refresh_gene_tooltip_async = () => {};
    `;

    const code = `${shims}\n${source}\nmodule.exports = { get_tooltip, hide_tooltip };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ get_tooltip, hide_tooltip } = module.exports);
  });

  const make_viz_state = (height = 200) => {
    const root = document.createElement('div');
    const tooltip_outer = document.createElement('div');
    const tooltip_parent = document.createElement('div');
    const tooltip = document.createElement('div');

    tooltip.className = 'deck-tooltip';
    tooltip.style.marginTop = '50px';
    tooltip.style.marginLeft = '12px';
    tooltip_outer.style.position = 'relative';
    tooltip_parent.appendChild(tooltip);
    tooltip_outer.appendChild(tooltip_parent);
    root.appendChild(tooltip_outer);

    Object.defineProperty(root, 'clientHeight', {
      value: height,
      configurable: true,
    });

    return {
      root,
      tooltip,
      tooltip_outer,
      viz_state: {
        root,
      },
    };
  };

  const dendro_object = {
    properties: {
      name: 'cluster-a',
      all_names: ['cell-a', 'cell-b'],
    },
  };

  test('column dendrogram tooltip is offset above the cursor by default', () => {
    const { tooltip, tooltip_outer, viz_state } = make_viz_state();

    const result = get_tooltip(viz_state, {
      object: dendro_object,
      layer: { id: 'col-dendro-layer' },
      y: 100,
    });

    expect(result.html).toContain('Column dendrogram: cluster-a');
    expect(result.style.translate).toBe('8px calc(-100% - 8px)');
    expect(tooltip.style.marginTop).toBe('0px');
    expect(tooltip.style.marginLeft).toBe('0px');
    expect(tooltip_outer.style.position).toBe('unset');
  });

  test('dendrogram tooltip truncates large member lists', () => {
    const { viz_state } = make_viz_state();
    const names = Array.from({ length: 15 }, (_, index) => `cell-${index}`);

    const result = get_tooltip(viz_state, {
      object: {
        properties: {
          name: '<cluster-a>',
          all_names: names,
        },
      },
      layer: { id: 'row-dendro-layer' },
      y: 100,
    });

    expect(result.html).toContain('Row dendrogram: &lt;cluster-a&gt;');
    expect(result.html).toContain('cell-0');
    expect(result.html).toContain('cell-11');
    expect(result.html).not.toContain('cell-12');
    expect(result.html).toContain('+3 more (15 total)');
  });

  test('dendrogram tooltip placement avoids top and bottom edges', () => {
    const { viz_state } = make_viz_state();

    const column_near_top = get_tooltip(viz_state, {
      object: dendro_object,
      layer: { id: 'col-dendro-layer' },
      y: 20,
    });
    const row_near_bottom = get_tooltip(viz_state, {
      object: dendro_object,
      layer: { id: 'row-dendro-layer' },
      y: 190,
    });
    const row_mid_view = get_tooltip(viz_state, {
      object: dendro_object,
      layer: { id: 'row-dendro-layer' },
      y: 100,
    });

    expect(column_near_top.style.translate).toBe('8px 8px');
    expect(row_near_bottom.style.translate).toBe('8px calc(-100% - 8px)');
    expect(row_mid_view.style.translate).toBe('8px 8px');
  });

  test('non-dendrogram tooltips reset custom offsets', () => {
    const { viz_state } = make_viz_state();

    const result = get_tooltip(viz_state, {
      object: { name: 'row-a' },
      layer: { id: 'row-label-layer' },
      y: 100,
    });

    expect(result.style.marginTop).toBe('0px');
    expect(result.style.marginLeft).toBe('0px');
    expect(result.style.translate).toBe('0 0');
  });

  test('crop drag hides the current tooltip and suppresses new content', () => {
    const { tooltip, viz_state } = make_viz_state();
    tooltip.innerHTML = 'stale';
    viz_state.crop = { drag: {} };

    const result = get_tooltip(viz_state, {
      object: { name: 'row-a' },
      layer: { id: 'row-label-layer' },
      y: 100,
    });

    expect(result).toBeNull();
    expect(tooltip.innerHTML).toBe('');
    expect(tooltip.style.display).toBe('none');
  });

  test('hide_tooltip clears tooltip content immediately', () => {
    const { tooltip, viz_state } = make_viz_state();
    tooltip.innerHTML = 'stale';

    hide_tooltip(viz_state);

    expect(tooltip.innerHTML).toBe('');
    expect(tooltip.style.display).toBe('none');
  });
});
