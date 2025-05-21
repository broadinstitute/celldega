export const get_image_dimensions = async (base_url, image_name, options, aws) => {

    const dzi_url = `${base_url}/pyramid_images/${image_name}.dzi`;

    // const dzi_url = 'http://localhost:60366/data/h_and_e_landscape/colon_h&e/pyramid_images/h_and_e.dzi'

    // const dzi_url = 'http://localhost:60366/data/xenium_landscapes/Xenium_Prime_Human_Skin_FFPE_outs/pyramid_images/dapi.dzi'

    console.log('get_image_dimensions', dzi_url);

    const response = aws !== null
        ? await aws.fetch(dzi_url)
        : await fetch(dzi_url, options.fetch);

    const xmlText = await response.text();
    const dziXML = new DOMParser().parseFromString(xmlText, 'text/xml');

    const dimensions = {
        height: Number(dziXML.getElementsByTagName('Size')[0].attributes.Height.value),
        width: Number(dziXML.getElementsByTagName('Size')[0].attributes.Width.value),
        tileSize: Number(dziXML.getElementsByTagName('Image')[0].attributes.TileSize.value)
    };

    console.log()

    return dimensions;
};
