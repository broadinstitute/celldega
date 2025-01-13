export const get_scatter_data = (arrow_table) => {
    try {

        const flatCoordinateArray = arrow_table.getChild("geometry").getChildAt(0).data
            .map(x => x.values)
            .reduce((acc, val) => {
                const combined = new Float64Array(acc.length + val.length);
                combined.set(acc);
                combined.set(val, acc.length);
                return combined;
            }, new Float64Array(0));

        // console.log(flatCoordinateArray/2)

        const scatter_data = {
            length: arrow_table.numRows,
            attributes: {
                getPosition: { value: flatCoordinateArray, size: 2 },
                // position: { value: flatCoordinateArray, size: 2 },
            }
        };

        return scatter_data
    } catch (error) {
        console.error("Error loading data:", error);
        return [];
    }
};