export const get_image_dimensions = async (base_url, image_name, options) => {

    const dzi_url = `${base_url}/pyramid_images/${image_name}.image.dzi`
    const response = await fetch(dzi_url, options.fetch)
    const xmlText = await response.text()
    const dziXML = new DOMParser().parseFromString(xmlText, 'text/xml')

    const dimensions = {
        height: Number(dziXML.getElementsByTagName('Size')[0].attributes.Height.value),
        width: Number(dziXML.getElementsByTagName('Size')[0].attributes.Width.value),
        tileSize: Number(dziXML.getElementsByTagName('Image')[0].attributes.TileSize.value)
  };        

  return dimensions

}