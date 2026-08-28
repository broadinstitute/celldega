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
      .replace(/^export const /gm, 'const ');

    const code = `${source}\nmodule.exports = { get_tooltip, hide_tooltip };`;
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
