/* global require */
const fs = require('fs');
const path = require('path');

class OrthographicView {
  constructor(props) {
    this.id = props.id;
    this.props = props;
  }
}

class OrthographicController {}

const source = fs
  .readFileSync(path.join(__dirname, '../deck-gl/matrix/views.js'), 'utf8')
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
  .replace(/^export const /gm, 'const ');
const api = new Function(
  'OrthographicView',
  'OrthographicController',
  'get_axis_display_count',
  'get_default_pan',
  'get_default_pan_y',
  `${source}; return { get_dendro_tree_views, get_dendro_tree_view_states };`
)(
  OrthographicView,
  OrthographicController,
  () => 2,
  () => [150, 100],
  () => 100
);

describe('temporary dendrogram overlay views', () => {
  const state = {
    viz: {
      row_region: 75,
      col_region: 60,
      label_buffer: 5,
      mat_width: 300,
      mat_height: 200,
    },
  };

  test('all passes occupy the matrix region in the existing Deck', () => {
    const views = api.get_dendro_tree_views(state);
    expect(views.map((view) => view.id)).toEqual([
      'dendro_tree_backdrop',
      'dendro_tree_rows',
      'dendro_tree_cols',
      'dendro_tree_foreground',
    ]);
    views.forEach((view) =>
      expect(view.props).toMatchObject({
        x: '80px',
        y: '65px',
        width: '300px',
        height: '200px',
      })
    );
    expect(views[0].props.viewState).toBe('dendro_tree_static');
    expect(views[3].props.viewState).toBe('dendro_tree_static');
    expect(views[0].props.controller).toBe(false);
    expect(views[3].props.controller).toBe(false);
    expect(views[1].props.controller).toMatchObject({
      type: expect.any(Function),
      scrollZoom: false,
      dragPan: false,
      keyboard: false,
    });
    expect(views[2].props.controller).toEqual(views[1].props.controller);
    expect(
      Object.create(views[1].props.controller.type.prototype).handleEvent()
    ).toBe(false);
  });

  test('only the leaf axis follows matrix zoom and pan', () => {
    expect(api.get_dendro_tree_view_states(state, [2, 3], [111, 222])).toEqual({
      dendro_tree_static: { target: [150, 100], zoom: [0, 0] },
      dendro_tree_rows: { target: [150, 222], zoom: [0, 3] },
      dendro_tree_cols: { target: [111, 100], zoom: [2, 0] },
    });
  });
});
