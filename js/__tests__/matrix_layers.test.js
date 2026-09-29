/* global require */

describe('get_mat_layers_list', () => {
  let get_mat_layers_list;
  let layer_filter;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');

    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/matrix/matrix_layers.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');

    const shims = `
      const crop_fade_signature = () => '';
      const crop_filter_signature = () => '';
    `;
    const code = `${shims}\n${source}\nmodule.exports = { get_mat_layers_list, layer_filter };`;
    const module = { exports: {} };
    new Function('module', 'exports', code)(module, module.exports);
    ({ get_mat_layers_list, layer_filter } = module.exports);
  });

  const make_layer = (id) => ({
    id,
    props: {
      transitions: {
        getPosition: { duration: 250 },
      },
    },
    clone(props = {}) {
      return {
        ...this,
        props: {
          ...this.props,
          ...props,
        },
        clone: this.clone,
      };
    },
  });

  test('snaps annotation transitions without changing matrix body or dendrograms', () => {
    const layers_mat = {
      mat_layer: make_layer('mat-layer'),
      row_cat_layer: make_layer('row-layer'),
      col_cat_layer: make_layer('col-layer'),
      row_label_layer: make_layer('row-label-layer'),
      col_label_layer: make_layer('col-label-layer'),
      row_dendro_layer: make_layer('row-dendro-layer'),
      col_dendro_layer: make_layer('col-dendro-layer'),
      row_attr_label_layer: make_layer('row-attr-label-layer'),
      col_attr_label_layer: make_layer('col-attr-label-layer'),
    };

    const layers = get_mat_layers_list(layers_mat, {
      snap_annotations: true,
    });
    const by_id = new Map(layers.map((layer) => [layer.id, layer]));

    expect(by_id.get('mat-layer').props.transitions).not.toBe(false);
    expect(by_id.get('row-dendro-layer').props.transitions).not.toBe(false);
    expect(by_id.get('col-dendro-layer').props.transitions).not.toBe(false);
    expect(by_id.get('row-layer').props.transitions).toBe(false);
    expect(by_id.get('col-layer').props.transitions).toBe(false);
    expect(by_id.get('row-label-layer').props.transitions).toBe(false);
    expect(by_id.get('col-label-layer').props.transitions).toBe(false);
    expect(by_id.get('row-attr-label-layer').props.transitions).toBe(false);
    expect(by_id.get('col-attr-label-layer').props.transitions).toBe(false);
  });

  test('includes and routes temporary tree layers through overlay views', () => {
    const layers_mat = {
      mat_layer: make_layer('mat-layer'),
      row_cat_layer: make_layer('row-layer'),
      col_cat_layer: make_layer('col-layer'),
      row_label_layer: make_layer('row-label-layer'),
      col_label_layer: make_layer('col-label-layer'),
      row_dendro_layer: make_layer('row-dendro-layer'),
      col_dendro_layer: make_layer('col-dendro-layer'),
      dendro_tree_background_layer: make_layer('dendro-tree-background-layer'),
      row_dendro_tree_branches_layer: make_layer(
        'row-dendro-tree-branches-layer'
      ),
      col_dendro_tree_branches_layer: make_layer(
        'col-dendro-tree-branches-layer'
      ),
      dendro_tree_water_layer: make_layer('dendro-tree-water-layer'),
      dendro_tree_cut_outline_layer: make_layer(
        'dendro-tree-cut-outline-layer'
      ),
      dendro_tree_cut_layer: make_layer('dendro-tree-cut-layer'),
      dendro_tree_caption_layer: make_layer('dendro-tree-caption-layer'),
    };
    const layers = get_mat_layers_list(layers_mat);
    expect(layers.map((layer) => layer.id)).toEqual(
      expect.arrayContaining([
        'dendro-tree-background-layer',
        'row-dendro-tree-branches-layer',
        'col-dendro-tree-branches-layer',
        'dendro-tree-water-layer',
        'dendro-tree-caption-layer',
      ])
    );
    expect(
      layer_filter({
        viewport: { id: 'dendro_tree_rows' },
        layer: layers_mat.row_dendro_tree_branches_layer,
      })
    ).toBe(true);
    expect(
      layer_filter({
        viewport: { id: 'matrix' },
        layer: layers_mat.row_dendro_tree_branches_layer,
      })
    ).toBe(false);
    expect(
      layer_filter({
        viewport: { id: 'dendro_tree_foreground' },
        layer: layers_mat.dendro_tree_caption_layer,
      })
    ).toBe(true);
  });
});
