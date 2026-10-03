export const set_image_format = (img, format) => {
  img.image_format = format;
};

const isPointCloudFamily = (technology = '') =>
  typeof technology === 'string' &&
  (technology === 'point-cloud' || technology.startsWith('point-cloud-'));

const isNeighborhoodCloudFamily = (technology = '') =>
  typeof technology === 'string' &&
  (technology === 'neighborhood-cloud' ||
    technology.startsWith('neighborhood-cloud-'));

// True for any 3D-orbit, load-nothing-whole-dataset-into-the-UI technology
// (point-cloud and neighborhood-cloud families). Most call sites only care
// about this shared behavior (OrbitView, no image layer, no 2D tiling, etc.);
// use is_neighborhood_cloud_technology below for the few places that must
// diverge between the two.
export const is_orbit_technology = (technology = '') =>
  isPointCloudFamily(technology) || isNeighborhoodCloudFamily(technology);

export const is_neighborhood_cloud_technology = (technology = '') =>
  isNeighborhoodCloudFamily(technology);

export const technology_has_image_layer = (technology = '') => {
  return technology !== 'Chromium' && !is_orbit_technology(technology);
};

export const get_landscape_image_info = (landscape_parameters = {}) => {
  if (!technology_has_image_layer(landscape_parameters.technology)) {
    return [];
  }

  return Array.isArray(landscape_parameters.image_info)
    ? landscape_parameters.image_info
    : [];
};

export const get_primary_image_name = (landscape_parameters = {}) => {
  return get_landscape_image_info(landscape_parameters)[0]?.name ?? null;
};

export const set_image_info = (img, info) => {
  img.image_info = Array.isArray(info) ? info : [];
  img.image_source = 'primary';
};

export const get_aligned_he = (img) => {
  const he = img.landscape_parameters?.aligned_he;
  return he && typeof he.name === 'string' && he.name.length > 0 ? he : null;
};

export const is_rgb_image = (info) =>
  info.image_source === 'he' || ['h_and_e', 'h&e'].includes(info.name);

export const get_image_sources = (img) => {
  const primary = img.image_info.map((info) => ({
    ...info,
    image_source: 'primary',
  }));
  const he = get_aligned_he(img);
  return he ? [...primary, { ...he, image_source: 'he' }] : primary;
};

export const set_image_layer_colors = (image_layer_colors, image_info = []) => {
  Object.keys(image_layer_colors).forEach((name) => {
    delete image_layer_colors[name];
  });

  image_info.forEach((info) => {
    image_layer_colors[info.button_name] = info.color;
  });
};
