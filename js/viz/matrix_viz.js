import { ini_deck } from '../deck-gl/deck_mat.js'


import {picking, COORDINATE_SYSTEM} from 'deck.gl'
import { Model, Geometry, Buffer } from '@luma.gl/engine';

console.log('Model')
console.log(Model)

import { ScatterplotLayer, TextLayer, OrthographicView, Layer } from 'deck.gl';

export const matrix_viz = async (
    model,
    el,
    // token,
) => {
    console.log('matrix_viz!!!!!!!!!')
    console.log('model', model)
    console.log('el', el)


    let viz_state = {}


    // Create and append the visualization.
    let root = document.createElement("div")
    root.style.height = "800px"

    let deck_mat = ini_deck(root)

    console.log('deck_mat')
    console.log(deck_mat)

    //////////////////////////////
    // Constants
    //////////////////////////////
    const mat_width = 600
    const mat_height = 600

    const num_rows = 10
    const num_cols = 10

    const base_font_size = 100

    const col_label_height = 20
    const row_region_width = 90

    const extra_height_col = 20

    const ini_zoom_x = 0
    const ini_zoom_y = 0

    const row_label_width = 30

    const row_cat_width = 9
    const col_cat_height = 9

    // width of row category bars
    const row_cat_offset = 10

    const num_cats_col = 3

    // height of column category bars
    const col_cat_offset = 10

    // position the cats
    const label_row_x = 15

    // position the cats
    const label_col_y = 25

    const cat_shift_row = 30

    const label_buffer = 1


    //////////////////////////////
    // Variables
    //////////////////////////////
    const ini_font_size = base_font_size / num_rows

    let inst_font_size = ini_font_size

    const row_height = mat_height/num_rows
    const col_region_height = col_cat_height * num_cats_col + col_label_height + extra_height_col
    const col_width = mat_width/num_cols
    const row_offset = mat_height/num_rows
    const col_offset = mat_width/num_cols


    // column category positioning
    const cat_shift_col = col_label_height // + extra_height_col
    const ini_pan_x = mat_width/2

    // not sure why I need to add row_offset?
    const ini_pan_y = mat_height/2 + row_offset

    const viz_width = mat_width + row_region_width

    const viz_height = mat_height + col_region_height

    //////////////////////////////
    // Data
    //////////////////////////////
    let matrix_index = 0;

    var index_row = 0

    var num_points = num_rows * num_cols

    // mat data
    const mat_data =  new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % num_cols

        if (matrix_index % num_cols === 0){
        index_row += 1;
        }

        var inst_red = parseInt(255 * (index_row/num_rows))
        var inst_blue = parseInt(255 * (index_col/num_cols))

        var inst_color
        if (index_col >= index_row){
            inst_color = [0, 0, 255]
        } else {
            inst_color = [255, 0, 0]
        }

        var inst_opacity = parseInt(255 * matrix_index/num_points)
        // var inst_opacity = 255 // parseInt(255 * matrix_index/num_points)

        const p = {
        position: [col_offset * index_col + col_offset/2, row_offset * index_row + row_offset/2],
        color: [inst_color[0], inst_color[1], inst_color[2], inst_opacity],
        value: ((index_row/num_rows) + (index_col/num_cols))/2,
        row: index_row,
        // seem to need to add index to col
        col: index_col + 1,
        };

        matrix_index += 1;

        return p;
    });

    // col label data
    matrix_index = 0;

    var index_col = 0

    var num_points = num_rows * 1

    const col_label_data =  new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % num_cols

        if (matrix_index % 1  === 0){
        index_col += 1;
        }

        const p = {
        position: [col_width * index_col - col_offset/2, col_label_height],
        name: 'col-' + index_col
        };

        matrix_index += 1;

        return p;
    });


    // row label data

    matrix_index = 0;

    var index_row = 0
    // const num_row_cats = 1

    var num_points = num_rows// * num_row_cats

    const row_label_data = new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % 1 // num_row_cats

        if (matrix_index % 1 == 0){ // num_row_cats =
        index_row += 1;
        }

        const p = {
        position: [row_label_width , row_offset * index_row + row_offset/2],
        name: 'row-' + index_row
        };

        matrix_index += 1;

        return p;
    });


    // row cat data
    matrix_index = 0;

    var index_row = 0
    const num_row_cats = 3

    var num_points = num_rows * num_row_cats

    const row_cat_data =  new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % num_row_cats

        if (matrix_index % num_row_cats === 0){
        index_row += 1;
        }

        const p = {
        position: [row_cat_offset * index_col, row_offset * index_row],
        color: [0, 255, 0, 255],
        name: 'something'
        };

        matrix_index += 1;

        return p;
    });

    // col cat data

    matrix_index = 0;

    var index_row = 0

    var num_points = num_cats_col * num_cols

    const col_cat_data = new Array(num_points).fill(0).map( _ => {

        var index_col = matrix_index % num_cols

        if (matrix_index % num_cols === 0){
        index_row += 1;
        }

        const p = {
        position: [col_offset * index_col, col_cat_offset * index_row],
        color: [0, 255, 0, 150],
        name: 'some column',
        };

        matrix_index += 1;

        return p;
    });


    //////////////////////////////
    // Custom Layer
    //////////////////////////////


    // Four corners of the quad
    const positions = new Float32Array([
        0,         0,
        0,         row_height,
        col_width, row_height,
        col_width, 0
    ]);

    console.log('positions', positions)


    // attribute vec3 positions;
    // attribute vec3 instancePositions;
    // attribute vec3 instancePositions64Low;
    // attribute vec4 instanceColors;

    // varying vec4 vColor;
    // varying vec2 vPosition;

    // attribute vec3 customPickingColors;

    // void main(void) {
    //   vec3 positionCommon = project_position(instancePositions + positions , instancePositions64Low);
    //   gl_Position = project_common_position_to_clipspace(vec4(positionCommon, 1.0));

    //   vPosition = positions.xy;
    //   vColor = instanceColors;

    //   picking_setPickingColor(customPickingColors);
    // }


    const vertexShader = `


    #version 300 es
    #define SHADER_NAME custom-layer-vertex-shader

    in vec3 positions;
    in vec3 instancePositions;
    in vec3 instancePositions64Low;
    in vec4 instanceColors;
    in vec3 customPickingColors;

    uniform float opacity;

    out vec4 vColor;
    out vec2 vPosition;

    void main(void) {
    geometry.worldPosition = instancePositions;

    // Use the updated function for projecting to clipspace
    gl_Position = project_position_to_clipspace(instancePositions, instancePositions64Low, positions, geometry.position);
    DECKGL_FILTER_GL_POSITION(gl_Position, geometry);

    // Pass the positions and colors to the fragment shader
    vPosition = positions.xy;
    vColor = vec4(instanceColors.rgb, instanceColors.a * opacity);
    DECKGL_FILTER_COLOR(vColor, geometry);

    // Set picking color
    geometry.pickingColor = customPickingColors;
    picking_setPickingColor(customPickingColors);
    }

    `

    // precision highp float;

    // varying vec4 vColor;
    // varying vec2 vPosition;

    // void main(void) {

    //   gl_FragColor = vec4(vColor.rgb, vColor.a);

    //   // Should be the last Fragment shader instruction that updates gl_FragColor
    //   gl_FragColor = picking_filterPickingColor(gl_FragColor);


    const fragmentShader = `



    #version 300 es
    #define SHADER_NAME custom-layer-fragment-shader

    precision highp float;

    in vec4 vColor;
    in vec2 vPosition;

    out vec4 fragColor;

    void main(void) {
    // Set the fragment color
    fragColor = vColor;

    // Apply picking filter
    fragColor = picking_filterPickingColor(fragColor);
    }


    }

    `


    const getMatrixModel = (gl) => {

        const geometry = new Geometry({
            drawMode: gl.TRIANGLE_FAN,
            vertexCount: 4,
            attributes: {
                positions: {
                    size: 2,
                    value: positions
                }
            }
        });

        return new Model(gl, {
            vs: vertexShader,
            fs: fragmentShader,
            geometry,
            isInstanced: true,
            // required for tooltip
            modules: [picking]
        });

    }


    class MatrixLayer extends Layer {

        initializeState() {

            const {gl} = this.context;

            // Register attributes
            this.getAttributeManager().addInstanced({
                instancePositions: {
                    size: 3,
                    type: gl.FLOAT,  // Changed from gl.DOUBLE to gl.FLOAT
                    accessor: 'getPosition'
                },
                instanceColors: {
                    size: 4,
                    normalized: true,
                    type: gl.UNSIGNED_BYTE,
                    accessor: 'getColor',
                    defaultValue: [0, 0, 0, 255]
                },
                // createing a picking color attribute
                customPickingColors: {
                    size: 3,
                    type: gl.UNSIGNED_BYTE,
                    update: this.calculatePickingColors
                    // update: calculatePickingColors
                }
            });

            // Save the model in layer state
            this.setState({
                model: getMatrixModel(gl)
            });
        }

        updateState() {
            // Retrieve the model from layer state
            this.state.model.setUniforms({
                // smoothRadius: this.props.smoothRadius
            });
        }

        //////////////////////////////////////////////////
        calculatePickingColors(attribute) {

            const {data} = this.props;
            const {value, size} = attribute;
            let i = 0;

            let index = 0;
            for (const object of data) {
                // console.log(index)

                // Use the index index instead of object.id
                const pickingColor = this.encodePickingColor(index);

                value[index * 3] = pickingColor[0];
                value[index * 3 + 1] = pickingColor[1];
                value[index * 3 + 2] = pickingColor[2];
                index++;
            }

        }
        //////////////////////////////////////////////////

    }

    const defaultProps = {

          // Center of each circle, in [longitude, latitude, (z)]
          getPosition: {type: 'accessor', value: x => x.position},

          // Color of each circle, in [R, G, B, (A)]
          // getColor: {type: 'accessor', value: [0, 0, 0, 255]},
          getColor: {type: 'accessor', value: [0, 0, 0, 50]},

      }


      MatrixLayer.layerName = 'MatrixLayer';
      MatrixLayer.defaultProps = defaultProps;

      const custom_layer = new MatrixLayer({
        id: 'matrix-layer',
        data: mat_data,
        getPosition: d => d.position,
        getColor: d => d.color,
        // getColor: d => [255, 0, 0, 50]

        // required for tooltip
        pickable: true,

        // onHover: (info, event) => console.log('Hovered:', info, event),
      });







    console.log('custom_layer')
    console.log(custom_layer)


    /////////////////////////////////////////////
    // very simple layer 9.0 compliant
    /////////////////////////////////////////////

    // Define a minimal vertex and fragment shader
    const vs = `#version 300 es
    in vec3 positions;
    void main(void) {
        gl_Position = vec4(positions, 1.0);
    }
    `;

    const fs = `#version 300 es
    precision highp float;
    out vec4 color;
    void main(void) {
        color = vec4(1.0, 0.0, 0.0, 1.0); // red color
    }
    `;

    // Define a custom TriangleLayer extending Layer
    class TriangleLayer extends Layer {

        // Initialize model using the new API
        initializeState() {
            this.state = {
                model: this.getModel({
                    isInstanced: true
                })
            };
        }

        getModel() {
            const { device } = this.context; // access device instead of gl context

            const geometry = new Geometry({
                drawMode: device.TRIANGLE_FAN,
                vertexCount: 3,
                attributes: {
                    positions: new Float32Array([
                        -0.5, -0.5, 0,
                        0.5, -0.5, 0,
                        0.0,  0.5, 0
                    ])
                }
            })

            return new Model(device, {
                vs,
                fs,
                geometry,
                // isInstanced: true,
                topology: 'triangle-list' // replaces GL.TRIANGLES
            });
        }

        draw({ uniforms }) {
            const { model } = this.state;
            model.draw({
                uniforms
            });
        }
    }

    console.log('TriangleLayer')
    console.log(TriangleLayer)

    TriangleLayer.layerName = 'MatrixLayer';

    const triangle_layer = new TriangleLayer({
        id: 'matrix-layer',
        coordinateSystem: COORDINATE_SYSTEM.CARTESIAN
    });

    console.log('triangle_layer', triangle_layer)


    //////////////////////////////
    // Layers
    //////////////////////////////

    class SquareScatterplotLayer extends ScatterplotLayer {
        getShaders() {
          // Get the default shaders from ScatterplotLayer
          const shaders = super.getShaders();

          // Customize the fragment shader to create square-shaped points
          shaders.fs = `#version 300 es
          #define SHADER_NAME scatterplot-layer-fragment-shader
          precision highp float;
          in vec4 vFillColor;
          in vec2 unitPosition;
          out vec4 fragColor;
          void main(void) {
              geometry.uv = unitPosition;
              fragColor = vFillColor;
              DECKGL_FILTER_COLOR(fragColor, geometry);
          }`;

          shaders.vs = `#version 300 es
            #define SHADER_NAME scatterplot-layer-vertex-shader

            in vec3 positions;

            in vec3 instancePositions;
            in vec3 instancePositions64Low;
            in float instanceRadius;
            in float instanceLineWidths;
            in vec4 instanceFillColors;
            in vec4 instanceLineColors;
            in vec3 instancePickingColors;

            uniform float opacity;
            uniform int radiusUnits;
            uniform int lineWidthUnits;

            out vec4 vFillColor;
            out vec4 vLineColor;
            out vec2 unitPosition;
            out float outerRadiusPixels;

            void main(void) {
            geometry.worldPosition = instancePositions;

            // // Multiply out radius and clamp to limits
            // outerRadiusPixels = project_size_to_pixel( instanceRadius, radiusUnits);

            // fixed size scatterplot
            outerRadiusPixels = 10.0;

            // position on the containing square in [-1, 1] space
            unitPosition = positions.xy;

            geometry.uv = unitPosition;
            geometry.pickingColor = instancePickingColors;

            // vec3 offset = positions * project_pixel_size(outerRadiusPixels);
            // vec3 offset = positions;

            // // Adjust the offset to use scaleX and scaleY
            // vec3 offset = vec3(
            //     positions.x * project_pixel_size(outerRadiusPixels),
            //     positions.y * 3.0,
            //     positions.z * project_pixel_size(outerRadiusPixels)
            // );

            // Compute the offset, applying scaling only to the x-axis
            vec3 offset = vec3(
                positions.x * project_pixel_size(outerRadiusPixels), // Scale x component
                positions.y * outerRadiusPixels,                    // Keep y component fixed
                positions.z * project_pixel_size(outerRadiusPixels) // Scale z component if needed
            );

            gl_Position = project_position_to_clipspace(instancePositions, instancePositions64Low, offset, geometry.position);

            vFillColor = vec4(instanceFillColors.rgb, instanceFillColors.a * opacity);
            DECKGL_FILTER_COLOR(vFillColor, geometry);

            vLineColor = vec4(instanceLineColors.rgb, instanceLineColors.a * opacity);
            DECKGL_FILTER_COLOR(vLineColor, geometry);
            }`

          return shaders;
        }
      }

    // Create a new ScatterplotLayer using the input data
    const mat_layer = new SquareScatterplotLayer({
        id: 'matrix-layer',
        data: mat_data,
        getPosition: d => d.position, // Position of each point
        getFillColor: d => d.color,   // Color of each point
        getRadius: d => 1 * (mat_height/(2 * num_rows)),           // Radius of each point (adjust as needed)
        // radiusUnits: 'pixels',
        pickable: true,               // Enable picking for interactivity
        opacity: 0.8,                  // Set the opacity of the points
        antialiasing: false
    });


    const row_label_layer  = new TextLayer({
        id: 'row-label-layer',
        data: row_label_data, // This should be the same data source you used for your other layers
        getPosition: d => d.position,
        getText: d => d.name, // Replace 'label' with the property in your data that contains the text you want to display
        getSize: d => inst_font_size,
        getColor: [0, 0, 0], // Text color as an RGBA array
        getAngle: 0, // Optional: Text angle in degrees
        getTextAnchor: 'end', // middle
        getAlignmentBaseline: 'center',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        updateTriggers: {
          getSize: inst_font_size
        },
        pickable: true,
        // onHover: (info, event) => console.log('Hovered:', info), // , event
      })


    const col_label_layer  = new TextLayer({
        id: 'col-label-layer',
        data: col_label_data, // This should be the same data source you used for your other layers
        getPosition: d => d.position,
        getText: d => d.name,
        getSize: inst_font_size,
        getColor: [0, 0, 0], // Text color as an RGBA array
        getAngle: 45, // Optional: Text angle in degrees
        getTextAnchor: 'start', // middle
        getAlignmentBaseline: 'bottom',
        fontFamily: 'Arial',
        sizeUnits: 'pixels',
        updateTriggers: {
          getSize: inst_font_size
        },
        pickable: true,
        // onHover: (info, event) => console.log('Hovered:', info), // , event
      })

    // Create a new ScatterplotLayer using the input data
    const row_cat_layer = new SquareScatterplotLayer({
        id: 'row-layer',
        data: row_cat_data,
        // getPosition: d => d.position, // Position of each point
        getPosition: d => [d.position[0] + cat_shift_row, d.position[1]],
        getFillColor: d => d.color,   // Color of each point
        getRadius: d => 1,           // Radius of each point (adjust as needed)
        pickable: true,               // Enable picking for interactivity
        opacity: 0.8                  // Set the opacity of the points
    });

    // Create a new ScatterplotLayer using the input data
    const col_cat_layer = new SquareScatterplotLayer({
        id: 'col-layer',
        data: col_cat_data,
        getPosition: d => [d.position[0], d.position[1] + cat_shift_col],
        getFillColor: d => d.color,   // Color of each point
        getRadius: d => 1,           // Radius of each point (adjust as needed)
        pickable: true,               // Enable picking for interactivity
        opacity: 0.8                  // Set the opacity of the points
    });


    // const layers = [mat_layer, row_cat_layer, col_cat_layer, row_label_layer, col_label_layer]
    const layers = [triangle_layer, row_cat_layer, col_cat_layer, row_label_layer, col_label_layer]

    const views = [

        new OrthographicView({
          id: 'matrix',
          x: ( row_region_width + label_buffer)+ 'px',
          y: ( col_region_height + label_buffer) + 'px',
          width: mat_width + 'px',
          height: mat_height + 'px',
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'all'},
        }),

        new OrthographicView({
          id: 'rows',
          x: '0px',
          y: (col_region_height + label_buffer) + 'px',
          width: row_region_width + 'px',
          height: mat_height + 'px',
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'Y'},
        }),

        new OrthographicView({
          id: 'cols',
          x: (row_region_width + label_buffer) + 'px',
          y: '0px',
          width: mat_width + 'px',
          height: col_region_height + 'px',
          controller: {scrollZoom: true, inertia: false, zoomAxis: 'X'},
        }),

  ]


    // update zoom_data inplace
    // this takes as an input the mutable zoom_data
    const update_zoom_data = (zoom_data, viewId, zoom, target) => {

        if (viewId === 'matrix') {

            console.log('matrix')

            // update pans
            zoom_data.pan_x = target[0];
            zoom_data.pan_y = target[1];

            // update zooms
            zoom_data.zoom_x = zoom[0]
            zoom_data.zoom_y = zoom[1]

        } else if (viewId === 'cols') {

            console.log('cols')

            // update pan_x
            zoom_data.pan_x = target[0]

            // update zooms
            zoom_data.zoom_x = zoom[0]

            // // switch to y zoom
            // ////////////////////////
            // // update pan_x
            // zoom_data.pan_x = target[0]

            // // update zooms
            // zoom_data.zoom_y = zoom[1]

        } else if (viewId === 'rows') {

            console.log('rows')

            // update pan_y
            zoom_data.pan_y = target[1];

            // update zooms
            zoom_data.zoom_y = zoom[1]

        }
    }

    const ini_global_view_state = () => {

        let globalViewState = {
          matrix: {
            // target: target,
            target: [ini_pan_x, ini_pan_y],
            // zoom: [ini_zoom_x, ini_zoom_y],
            zoom: [ini_zoom_x, ini_zoom_y],
          },
          rows: {
            target: [label_row_x, ini_pan_y],
            zoom: [ini_zoom_x, ini_zoom_y],
          },
          cols: {
            target: [ini_pan_x, label_col_y],
            zoom: [ini_zoom_x, ini_zoom_y],
          },
        }

        return globalViewState

      }


    const layerFilter = ({layer, viewport}) => {

        // console.log(viewport.id, layer.id)
        if (viewport.id === 'matrix' && layer.id === 'matrix-layer'){
            return true
        } else if (viewport.id === 'rows' && layer.id === 'row-layer'){
            return true
        } else if (viewport.id === 'cols' && layer.id === 'col-layer'){
            return true
        } else if (viewport.id === 'rows' && layer.id === 'row-label-layer'){
            return true
        } else if (viewport.id === 'cols' && layer.id === 'col-label-layer'){
            return true
        }

        return false

        // return true
    }

    const getTooltip = ({object, layer}) => {
        if (object) {
          // Check which layer the tooltip is currently over
          if (layer.id === 'row-label-layer') {
            // Display the row label when hovering over the row_label_layer
            return {
              html: `Row Label: ${object.name}`,
              style: {color: "white"},
            };
          }
          else if (layer.id === 'col-label-layer') {
            // Display the row label when hovering over the row_label_layer
            return {
              html: `Col Label: ${object.name}`,
              style: {color: "white"},
            };
          }
          else if (layer.id === 'row-layer') {
            // Display the row label when hovering over the row_label_layer
            return {
              html: `Row Label: ${object.name}`,
              style: {color: "white"},
            };
          }
          else if (layer.id === 'col-layer') {
            // Display the row label when hovering over the row_label_layer
            return {
              html: `Col Label: ${object.name}`,
              style: {color: "white"},
            };
          }
          else if (layer.id === 'matrix-layer') {
            // Display the default tooltip for other layers
            return {
              html: `Row: ${object.row} <br> Column: ${object.col}`,
              style: {color: "white"},
            };
          }
        }
      }


    // trying to define a mutable zoom_data outside of the deckgl cell
    let zoom_data = ({
        pan_x: ini_pan_x,
        pan_y: ini_pan_y,
        zoom_x: ini_zoom_x,
        zoom_y: ini_zoom_y,
    })


    const ini_view_state = ini_global_view_state()

    const curate_pan_y = (target_y, zoom_curated_y, ini_pan_y) => {

        // ini_pan_y = ini_pan_y// - row_offset

        var pan_curated_y

        var zoom_factor_y = Math.pow(2, zoom_curated_y)

        // var min_pan_y = ini_pan_y/zoom_factor_y
        var min_pan_y = (ini_pan_y - row_offset)/zoom_factor_y + row_offset

        // calculating the shift to the min, to re-use for the max
        var min_diff = ini_pan_y - min_pan_y

        var max_pan_y = ini_pan_y + min_diff

        if (target_y <= min_pan_y){
          // console.log('below min')
          pan_curated_y = min_pan_y
        } else if (target_y > max_pan_y) {
          pan_curated_y = max_pan_y
          // console.log('above min')
        } else {
          pan_curated_y = target_y
          // console.log('within bounds')
        }

        return pan_curated_y// + row_offset
      }

    const curate_pan_x = (target_x, zoom_curated_x, ini_pan_x) => {

        var pan_curated_x

        var zoom_factor_x = Math.pow(2, zoom_curated_x)

        var min_pan_x = ini_pan_x/zoom_factor_x

        // calculating the shift to the min, to re-use for the max
        var min_diff = ini_pan_x - min_pan_x

        var max_pan_x = ini_pan_x + min_diff

        if (target_x <= min_pan_x){
            // console.log('below min')
            pan_curated_x = min_pan_x
        } else if (target_x > max_pan_x) {
            pan_curated_x = max_pan_x
            // console.log('above min')
        } else {
            pan_curated_x = target_x
            // console.log('within bounds')
        }

        return pan_curated_x

    }


    // new version with fewer arguments
    // this does not need the mutable zoom_data since it
    // is not going to be modifying zoom_data
    const redefine_global_view_state = (zoom_data, viewId, zoom, target) => {

        var globalViewState

        var min_zoom_x = 0
        var min_zoom_y = 0
        var zoom_curated_x = Math.max(min_zoom_x, zoom[0])
        var zoom_curated_y = Math.max(min_zoom_x, zoom[1])

        var pan_curated_x = curate_pan_x(target[0], zoom_curated_x, ini_pan_x)
        // var pan_curated_y = ini_pan_y // target[1]
        var pan_curated_y = curate_pan_y(target[1], zoom_curated_y, ini_pan_y)

        if (viewId === 'matrix') {

        globalViewState = {
            matrix: {
            // zoom: [zoom[0], zoom[1]],
            zoom: [zoom_curated_x, zoom_curated_y],
            // target: [target[0], target[1]]
            target: [pan_curated_x, pan_curated_y]
            },
            rows:   {
            // zoom: [ini_zoom_x, zoom[1]],
            zoom: [ini_zoom_x, zoom_curated_y],
            // target: [label_row_x, target[1]]
            target: [label_row_x, pan_curated_y]
            },
            cols:   {
            // zoom: [zoom[0], ini_zoom_y],
            zoom: [zoom_curated_x, ini_zoom_y],
            // target: [target[0], label_col_y]
            target: [pan_curated_x, label_col_y]
            },
        }

        } else if (viewId === 'cols'){

        globalViewState = {
            matrix: {
            // zoom: [zoom[0], zoom_data.zoom_y],
            zoom: [zoom_curated_x, zoom_data.zoom_y],
            // target: [target[0], zoom_data.pan_y]
            target: [pan_curated_x, zoom_data.pan_y]
            },
            rows:   {
            // zoom: [ini_zoom_x, zoom_data.zoom_y],
            zoom: [ini_zoom_x, zoom_data.zoom_y],
            // target: [label_row_x, zoom_data.pan_y]
            target: [label_row_x, zoom_data.pan_y]
            },
            cols:   {
            // zoom: [zoom[0], ini_zoom_y],
            zoom: [zoom_curated_x, ini_zoom_y],
            // target: [target[0], label_col_y]
            target: [pan_curated_x, label_col_y]
            },
        }

        } else if (viewId === 'rows'){

        globalViewState = {
            matrix: {
            // zoom: [zoom_data.zoom_x, zoom[1]],
            zoom: [zoom_data.zoom_x, zoom_curated_y],
            // target: [zoom_data.pan_x, target[1]]
            target: [zoom_data.pan_x, pan_curated_y]
            },
            rows:   {
            // zoom: [ini_zoom_x, zoom[1]],
            zoom: [ini_zoom_x, zoom_curated_y],
            // target: [label_row_x, target[1]]
            target: [label_row_x, pan_curated_y]
            },
            cols:   {
            // zoom: [zoom_data.zoom_x, ini_zoom_y],
            zoom: [zoom_data.zoom_x, ini_zoom_y],
            // target: [zoom_data.pan_x, label_col_y]
            target: [zoom_data.pan_x, label_col_y]
            },
        }

        }

        return globalViewState
    }


    const on_view_state_change = ({viewState, viewId}) => {

        const {zoom, target, offset} = viewState;

        // this takes the latest non-mutable zoom_data since it does
        // not update zoom_data
        var global_view_state = redefine_global_view_state(zoom_data, viewId, zoom, target)

        var zoom_factor_x = Math.pow(2, zoom_data.zoom_x)

        inst_font_size = ini_font_size * zoom_factor_x

        // this takes mutable zoom_data since it updates zoom_data's state
        update_zoom_data(zoom_data, viewId, zoom, target)

        var updated_view_state = {...global_view_state}

        // this will only update the zoom state for the current layer
        // return updated_view_state

        // use setProps to update viewState with updated_view_state
        deck_mat.setProps({viewState: updated_view_state});

    }

    deck_mat.setProps({
        onViewStateChange: on_view_state_change,
        views: views,
        initialViewState: ini_view_state,
        getTooltip: getTooltip,
        layerFilter: layerFilter,
        layers: layers,
    })

    el.appendChild(root)

}