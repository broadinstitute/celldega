export const get_image_dimensions = async (
  base_url,
  image_name,
  options = {}, // Safe default
  aws = null // Safe default
) => {
  const dzi_url = `${base_url}/pyramid_images/${image_name}.dzi`;
  console.log('🔍 dzi_url:', dzi_url);

  let fetchFn;
  let fetchOptions;

  // Handle AWS fetch case
  if (aws && typeof aws.fetch === 'function') {
    fetchFn = aws.fetch;
    fetchOptions = undefined; // aws.fetch usually includes its own signing logic
  } else {
    // Use custom fetch if provided, else fall back to global fetch
    fetchFn = typeof options.fetch === 'function' ? options.fetch : fetch;
    fetchOptions = options.requestOptions ?? {}; // Allow passing requestOptions
  }

  let response;
  try {
    response = await fetchFn(dzi_url, fetchOptions);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} - ${response.statusText}`);
    }
  } catch (error) {
    console.error('❌ Fetch failed:', {
      url: dzi_url,
      error: error.message,
    });
    throw error;
  }

  const xmlText = await response.text();
  const dziXML = new DOMParser().parseFromString(xmlText, 'text/xml');

  const dimensions = {
    height: Number(
      dziXML.getElementsByTagName('Size')[0].attributes.Height.value
    ),
    width: Number(
      dziXML.getElementsByTagName('Size')[0].attributes.Width.value
    ),
    tileSize: Number(
      dziXML.getElementsByTagName('Image')[0].attributes.TileSize.value
    ),
  };

  console.log('📐 Parsed image dimensions:', dimensions);
  return dimensions;
};
