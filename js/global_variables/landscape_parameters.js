import { options } from './fetch_options';

export const set_landscape_parameters = async (
  img,
  base_url,
  aws,
  manifest_name = 'landscape_parameters.json'
) => {
  const fetch_manifest = (name) => {
    const url = `${base_url}/${name}`;
    return aws ? aws.fetch(url) : fetch(url, options.fetch);
  };

  let response = await fetch_manifest(manifest_name);

  // Fall back to the legacy manifest name so DegaFiles built before the
  // cell_cloud.json / neighborhood_cloud.json rename still render.
  if (!response.ok && manifest_name !== 'landscape_parameters.json') {
    response = await fetch_manifest('landscape_parameters.json');
  }

  if (!response.ok) {
    throw new Error(
      `Failed to fetch ${manifest_name}: ${response.status} ${response.statusText}`
    );
  }

  img.landscape_parameters = await response.json();
};
