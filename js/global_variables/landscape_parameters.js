import { options } from './fetch_options';

export const set_landscape_parameters = async (img, base_url, aws) => {
  const landscape_parameters_url = `${base_url}/landscape_parameters.json`;
  const response = aws
    ? await aws.fetch(landscape_parameters_url)
    : await fetch(landscape_parameters_url, options.fetch);

  if (!response.ok) {
    throw new Error(
      `Failed to fetch landscape_parameters.json: ${response.status} ${response.statusText}`
    );
  }

  img.landscape_parameters = await response.json();
};
