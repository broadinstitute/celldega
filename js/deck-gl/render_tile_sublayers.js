// export const render_tile_sublayers = (props) => {
//     const {
//         bbox: {left, bottom, right, top}
//     } = props.tile;
//     const {width, height} = dimensions;

//     return new CustomBitmapLayer(props, {
//         data: null,
//         image: props.data,
//         bounds: [
//             mathGl.clamp(left, 0, width),
//             mathGl.clamp(bottom, 0, height),
//             mathGl.clamp(right, 0, width),
//             mathGl.clamp(top, 0, height)
//         ],
//         color: [255, 0, 0], // Custom color
//         opacityScale: 3.0, // Custom opacity scale
//     });

// }