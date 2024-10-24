import { options } from './fetch_options.js'

export const set_landscape_parameters = async (img, base_url) => {

    const landscape_parameters_url = base_url + '/landscape_parameters.json'
    const response = await fetch(landscape_parameters_url, options.fetch)
    img.landscape_parameters = await response.json()

}