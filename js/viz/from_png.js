import { read_png } from './png';
import { source_options } from './source';

const object = (value) => value && typeof value === 'object' && !Array.isArray(value);

/** Validate and resolve one panel before any constructor fetches source data. */
export const png_panel = (record, { panel = 0, allow_resize = false, ...overrides } = {}) => {
  if (!Number.isInteger(panel) || panel < 0 || panel >= record.widgets.length)
    throw new Error('PNG panel index is out of range');
  if (typeof allow_resize !== 'boolean') throw new Error('allow_resize must be boolean');
  const entry = record.widgets[panel];
  const saved = entry?.snapshot;
  if (saved?.schema !== 'celldega.view' || saved.version !== 2)
    throw new Error('Unsupported saved-view schema/version');
  if (!['landscape', 'clustergram'].includes(saved.kind) || !object(saved.state) || !object(saved.identity) || !Object.keys(saved.identity).length)
    throw new Error('PNG panel has no supported replay state and data identity');
  const source = { ...saved.source, ...entry.source };
  const options = source_options({ ...saved.source?.options, ...entry.source?.options }, saved.kind);
  const selectors = saved.kind === 'clustergram' ? ['network', 'url', 'base_url'] : ['zarr_url', 'base_url', 'base_urls'];
  if (selectors.some((key) => key in overrides)) selectors.forEach((key) => delete options[key]);
  Object.assign(options, overrides);
  const supplied_data = selectors.some((key) => key in overrides && overrides[key]);
  if (source.requires_data && !supplied_data)
    throw new Error('This PNG used in-memory data; supply the original network or source options');
  if (saved.kind === 'clustergram' && !options.network && !options.url && !options.base_url)
    throw new Error('This PNG has no reconstructable Clustergram source; supply network, url or base_url');
  if (saved.kind === 'landscape' && !options.zarr_url && !options.base_url && !options.base_urls?.length)
    throw new Error('This PNG has no reconstructable Landscape source; supply base_url or zarr_url');
  if (saved.kind === 'landscape') {
    if (source.widget === 'CellCloud') options.technology ??= 'point-cloud';
    if (source.widget === 'NeighborhoodCloud') options.technology ??= 'neighborhood-cloud';
    if (!options.technology && !options.zarr_url)
      throw new Error('This PNG does not record its technology; supply technology explicitly');
  }
  // Legacy records only have canvas dimensions. Clustergram adds 100 px of
  // label margins to each constructor dimension (deck-gl/matrix/deck_mat.js).
  const margin = saved.kind === 'clustergram' ? 100 : 0;
  for (const key of ['width', 'height']) {
    if (!(Number(options[key]) > 0) && Number(saved.viewport?.[key]) > margin)
      options[key] = Number(saved.viewport[key]) - margin;
  }
  return { saved, options, allow_resize };
};

/** Construct a fresh standalone visualization and acknowledge its restored view. */
export const create_from_png = ({ landscape, clustergram }) => async (el, input, settings = {}) => {
  const record = await read_png(input);
  const { saved, options, allow_resize } = png_panel(record, settings);
  const constructor = saved.kind === 'clustergram' ? clustergram : landscape;
  const viz = await constructor(el, options);
  try {
    await viz.restore_snapshot(saved, { allow_resize });
    return viz;
  } catch (error) {
    viz.finalize?.();
    throw error;
  }
};
