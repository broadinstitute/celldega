/* global require */

const fs = require('fs');
const path = require('path');

const {
  OrbitView,
  OrthographicView,
  OrbitController,
} = require('@deck.gl/core');

const readStripped = (file) =>
  fs
    .readFileSync(path.join(__dirname, '..', file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
const set_views = new Function(
  'OrbitView',
  'OrthographicView',
  `
  ${readStripped('global_variables/image_info.js')}
  ${readStripped('deck-gl/core/views.js')}
  return set_views;
`
)(OrbitView, OrthographicView);

describe('continuous OrbitView rotation', () => {
  test.each(['point-cloud', 'point-cloud-aligned', 'neighborhood-cloud'])(
    '%s rotates through multiple turns on both axes',
    (technology) => {
      const [view] = set_views(technology);
      const controller = new OrbitController({});
      let state = new controller.ControllerState(
        view.filterViewState({
          width: 800,
          height: 600,
          target: [1, 2, 3],
          zoom: 0,
          rotationX: 0,
          rotationOrbit: 0,
          makeViewport: (props) =>
            view.makeViewport({
              viewState: props,
              width: 800,
              height: 600,
            }),
        })
      );

      for (let i = 1; i <= 100; i++) {
        state = state.rotateDown(15).rotateRight(15);
        const props = state.getViewportProps();
        expect(props.rotationX).toBe(i * 15);
        expect(
          view
            .makeViewport({ viewState: props, width: 800, height: 600 })
            .viewMatrix.every(Number.isFinite)
        ).toBe(true);
      }
      for (let i = 0; i < 200; i++) state = state.rotateUp(15).rotateLeft(15);
      expect(state.getViewportProps().rotationX).toBe(-1500);
      expect(state.getViewportProps().target).toEqual([1, 2, 3]);
      controller.finalize();
    }
  );

  test('programmatic camera resets retain unrestricted pitch', () => {
    const [view] = set_views('point-cloud');
    const props = view.filterViewState({
      rotationX: 225,
      minRotationX: -90,
      maxRotationX: 90,
    });
    expect(props.rotationX).toBe(225);
    expect(props.minRotationX).toBe(-Infinity);
    expect(props.maxRotationX).toBe(Infinity);
  });

  test('2D views remain orthographic', () => {
    const [view] = set_views('Xenium');
    expect(view).toBeInstanceOf(OrthographicView);
    expect(view.props.viewState).toBeUndefined();
  });
});
