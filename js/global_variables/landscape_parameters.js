import { options } from './fetch_options';

export const set_landscape_parameters = async (img, base_url, _aws) => {
  const landscape_parameters_url = `${base_url}/landscape_parameters.json`;
  const response = await fetch(landscape_parameters_url, options.fetch);
  img.landscape_parameters = await response.json();
};
