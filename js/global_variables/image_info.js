export const set_image_format = (img, format) => {
  img.image_format = format;
};

export const is_point_cloud_technology = (technology = '') => {
  return (
    typeof technology === 'string' &&
    (technology === 'point-cloud' ||
      technology.startsWith('point-cloud-'))
  );
};

export const technology_has_image_layer = (technology = '') => {
  return technology !== 'Chromium' && !is_point_cloud_technology(technology);
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
};

export const set_image_layer_colors = (
  image_layer_colors,
  image_info = []
) => {
  Object.keys(image_layer_colors).forEach((name) => {
    delete image_layer_colors[name];
  });

  image_info.forEach((info) => {
    image_layer_colors[info.button_name] = info.color;
  });
};
