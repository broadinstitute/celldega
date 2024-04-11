export const concatenate_polygon_data = (dataObjects) => {
    // Initialize concatenated data structure
    let concatenatedData = {
        length: 0,
        startIndices: new Int32Array(),
        attributes: {
            getPolygon: {
                value: new Float64Array(),
                size: 2 // Assuming 'size' remains constant
            }
        }
    };

    // Iterate over each data object to combine them
    dataObjects.forEach((data, index) => {
        concatenatedData.length += data.length;

        // Handle startIndices
        let lastValue = concatenatedData.attributes.getPolygon.value.length/2;
        let adjustedStartIndices = data.startIndices;

        if (index > 0) {
            // Adjust startIndices (except for the first data object)
            adjustedStartIndices = new Int32Array(data.startIndices.length);
            for (let i = 0; i < data.startIndices.length; i++) {
                adjustedStartIndices[i] = data.startIndices[i] + lastValue;
            }
        }

        // Combine startIndices and coordinate values
        concatenatedData.startIndices = new Int32Array([...concatenatedData.startIndices, ...adjustedStartIndices.slice(index > 0 ? 1 : 0)]);
        concatenatedData.attributes.getPolygon.value = new Float64Array([...concatenatedData.attributes.getPolygon.value, ...data.attributes.getPolygon.value]);
    });

    return concatenatedData;
}