export var options = {}

export const set_options = (token) => {
    options = {
        fetch: {
            headers: {
            'Authorization': `Bearer ${token}` // Use the token in the Authorization header
            }
        }
    }
    
    return options
}