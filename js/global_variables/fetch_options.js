export let options = {}

export const set_options = (token) => {

    // Initialize fetch options
    options = {
        fetch: {
            headers: {}
        }
    };

    // Conditionally add the Authorization header if the token is not empty
    if (token) {
        options.fetch.headers['Authorization'] = `Bearer ${token}`;
    }
};