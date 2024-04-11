export const hexToRgb = (hex) => {
    // Remove the hash at the start if it's there
    hex = hex.replace(/^#/, '');
    let r = 0, g = 0, b = 0;
    // 3 digits
    if (hex.length === 3) {
        r = parseInt(hex.charAt(0) + hex.charAt(0), 16);
        g = parseInt(hex.charAt(1) + hex.charAt(1), 16);
        b = parseInt(hex.charAt(2) + hex.charAt(2), 16);
    }
    // 6 digits
    else if (hex.length === 6) {
        r = parseInt(hex.substring(0, 2), 16);
        g = parseInt(hex.substring(2, 4), 16);
        b = parseInt(hex.substring(4, 6), 16);
    }
    return [r, g, b];
}