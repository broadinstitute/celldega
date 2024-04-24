import { options } from './fetch_options.js'

export let landscape_parameters = {}

export const set_landscape_parameters = async (base_url) => {

    const landscape_parameters_url = base_url + '/landscape_parameters.json'
    const response = await fetch(landscape_parameters_url, options.fetch)
    landscape_parameters = await response.json()

}