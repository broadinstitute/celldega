import "./widget.css";

import { Deck, ScatterplotLayer, TileLayer, BitmapLayer, OrthographicView, PathLayer } from 'deck.gl';
import { load } from '@loaders.gl/core';
import * as mathGl from 'math.gl';

import { visibleTiles } from "./vector_tile/visibleTiles.js";
import { concatenate_polygon_data, concatenate_arrow_tables } from "./vector_tile/concatenate_functions.js";
import { fetch_all_tables } from "./read_parquet/fetch_all_tables.js";
import { get_scatter_data } from "./read_parquet/get_scatter_data.js";
import { get_polygon_data } from "./read_parquet/get_polygon_data.js";
import { debounce } from "./utils/debounce.js";
import { extractPolygonPaths } from "./vector_tile/polygons/extractPolygonPaths.js";
import { hexToRgb } from "./utils/hexToRgb.js";

import { get_arrow_table } from "./read_parquet/get_arrow_table.js";

// import { grab_trx_tiles_in_view } from "./vector_tile/transcripts/grab_trx_tiles_in_view.js";

export async function render({ model, el }) {

    const cache_trx = new Map();
    const cache_cell = new Map();
    const base_url = model.get('base_url')
    

    // functions
    ////////////////

    // pattern for closure and factory
    const def_real_fun = ( test_variable ) => () => {
      console.log('real_fun', test_variable);
    };    

    // A test variable to be used in the function
    const test_variable = 'something with closures!!!!! and skipping create_real_fun';

    // Create a function using the factory
    const real_fun = def_real_fun(test_variable);

    // Execute the function created by the factory
    real_fun();

    let trx_names_array = [];

    const grab_trx_tiles_in_view = async (tiles_in_view, options) => {

      console.log('grab_trx_tiles_in_view')

      const tile_trx_urls = tiles_in_view.map(tile => {
        return `${base_url}/real_transcript_tiles_mosaic/transcripts_tile_${tile.tileX}_${tile.tileY}.parquet`;
      });
    
      var tile_trx_tables = await fetch_all_tables(cache_trx, tile_trx_urls, options)
      var trx_arrow_table = concatenate_arrow_tables(tile_trx_tables)
      trx_names_array = trx_arrow_table.getChild("name").toArray();
      var trx_scatter_data = get_scatter_data(trx_arrow_table)
    
      // return  {
      //   trx_scatter_data, 
      //   trx_names_array
      // }
      return trx_scatter_data
    }


    // // Define a factory function that returns an async function
    // const def_grab_trx_tiles_in_view = (base_url, cache_trx, trx_names_array) => async (tiles_in_view, options) => {

    //   console.log('new grab_trx_ties_in_view')

    //   const tile_trx_urls = tiles_in_view.map(tile => `${base_url}/real_transcript_tiles_mosaic/transcripts_tile_${tile.tileX}_${tile.tileY}.parquet`);
  
    //   var tile_trx_tables = await fetch_all_tables(cache_trx, tile_trx_urls, options);
    //   var trx_arrow_table = concatenate_arrow_tables(tile_trx_tables);
    //   trx_names_array.length = 0;
    //   trx_names_array.push(...trx_arrow_table.getChild("name").toArray());
    //   var trx_scatter_data = get_scatter_data(trx_arrow_table);
  
    //   return trx_scatter_data;
    // };
  

    // const new_grab_trx_tiles_in_view = def_grab_trx_tiles_in_view(base_url, cache_trx, trx_names_array);


  

    const grab_cell_tiles_in_view = async (tiles_in_view) => {

        const tile_cell_urls = tiles_in_view.map(tile => {
            return `${base_url}/cell_segmentation_v2/cell_tile_${tile.tileX}_${tile.tileY}.parquet`;
        });

        var tile_cell_tables = await fetch_all_tables(cache_cell, tile_cell_urls, options)

        var polygon_datas = tile_cell_tables.map(x => get_polygon_data(x))

        // this can be used directly in the SolidPolygonLayer
        var polygon_data = concatenate_polygon_data(polygon_datas);

        var polygonPathsConcat = extractPolygonPaths(polygon_data)

        return polygonPathsConcat
    }

  

    const calc_viewport = async ({ height, width, zoom, target }, options) => {

        const zoomFactor = Math.pow(2, zoom);
        const [targetX, targetY] = target;
        const halfWidthZoomed = width / (2 * zoomFactor);
        const halfHeightZoomed = height / (2 * zoomFactor);

        const minX = targetX - halfWidthZoomed;
        const maxX = targetX + halfWidthZoomed;
        const minY = targetY - halfHeightZoomed;
        const maxY = targetY + halfHeightZoomed;

        const tiles_in_view = visibleTiles(minX, maxX, minY, maxY, tileSize);

        var num_tiles_to_viz = tiles_in_view.length

        if (num_tiles_to_viz < max_tiles_to_view) {

            // trx tiles
            ////////////////////////////////
            let trx_scatter_data = grab_trx_tiles_in_view(
              tiles_in_view, 
              options, 
              base_url, 
              cache_trx, 
              trx_names_array
            )

            const trx_layer_new = new ScatterplotLayer({
                // Re-use existing layer props
                ...trx_layer.props,
                data: trx_scatter_data,
            });

            // cell tiles
            ////////////////////////////////

            const polygonPathsConcat = grab_cell_tiles_in_view(tiles_in_view, options)

            const polygon_layer_new = new PathLayer({
                // Re-use existing layer props
                ...polygon_layer.props,
                data: polygonPathsConcat,
            });

            // console.log('cache_trx size', cache_trx.size)

            // update layer
            deck.setProps({
                // layers: [tile_layer, polygon_layer_new, cell_layer, trx_layer_new]
                layers: [tile_layer_2, tile_layer, polygon_layer_new, cell_layer, trx_layer_new]
                // layers: [tile_layer_2, tile_layer] // , trx_layer_new]
            });

        } else {
            deck.setProps({
                // layers: [tile_layer, cell_layer]
                layers: [tile_layer_2, tile_layer, cell_layer]
                // layers: [tile_layer_2, tile_layer]
            });
        }
    };


    const make_tooltip = (info) => {

      // Check if there's a valid index
      if (info.index === -1 || !info.layer) return null;

      let inst_name

      if (info.layer.id === 'cell-layer'){
          inst_name = cell_names_array[info.index]

      } else if (info.layer.id === 'trx-layer') {
         inst_name = trx_names_array[info.index]
      }

      // Make sure to check that `dataItem` and the property you want to display exist
      return {
        html: `<div>${inst_name}</div?`,
      };

    }



	

    // Deck.gl Viz
    const token = model.get('token_traitlet')
    const ini_x = model.get('ini_x');
    const ini_y = model.get('ini_y');
    const ini_zoom = model.get('ini_zoom');
    const max_image_zoom = model.get('max_image_zoom')
    const bounce_time = model.get('bounce_time')
	  

    // authorization token for bucket
    const options = ({
        fetch: {
          headers: {
            'Authorization': `Bearer ${token}` // Use the token in the Authorization header
          }
        }
      })

    const image_name = 'cellbound' // 'dapi' // 'brain';

    const dzi_url = `${base_url}/pyramid_images/${image_name}.image.dzi`
    const response = await fetch(dzi_url, options.fetch)
    const xmlText = await response.text()
    const dziXML = new DOMParser().parseFromString(xmlText, 'text/xml')


    // Image Code
    const dimensions = {
      height: Number(dziXML.getElementsByTagName('Size')[0].attributes.Height.value),
      width: Number(dziXML.getElementsByTagName('Size')[0].attributes.Width.value),
      tileSize: Number(dziXML.getElementsByTagName('Image')[0].attributes.TileSize.value)
    };

    class CustomBitmapLayer extends BitmapLayer {
      getShaders() {
        const shaders = super.getShaders();
        // Directly injecting shader code
        shaders.inject = {
          'fs:#decl': `uniform vec3 uColor; uniform float uOpacityScale;`,
          'fs:DECKGL_FILTER_COLOR': `
            // Convert color to grayscale and apply opacity scale
            float grayscale = ((color.r + color.g + color.b) / 3.0) * uOpacityScale;
            // Clamp grayscale to valid range
            grayscale = clamp(grayscale, 0.0, 1.0);
            // Apply custom color and scaled opacity
            color = vec4(uColor, grayscale);
          `
        };
        return shaders;
      }

      // Properly passing uniforms through updateState lifecycle hook
      updateState(params) {
        super.updateState(params);
        // Extracting custom props
        const {props, oldProps} = params;
        if (props.color !== oldProps.color || props.opacityScale !== oldProps.opacityScale) {
          // Update uniforms when props change
          this.setState({
            uniforms: {
              uColor: props.color.map(c => c / 255), // Normalize RGB to [0, 1] range
              uOpacityScale: props.opacityScale
            }
          });
        }
      }

      draw(opts) {
        // Ensuring custom uniforms are passed to the shader program
        const {uniforms} = this.state;
        super.draw({
          ...opts,
          uniforms: {
            ...opts.uniforms,
            ...uniforms, // Spread in custom uniforms
          },
        });
      }
    }

    const tile_layer = new TileLayer({
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20, // 5
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: ({index}) => {
            const {x, y, z} = index;
            const full_url = `${base_url}/pyramid_images/${image_name}.image_files/${max_image_zoom + z}/${x}_${y}.jpeg`;

            return load(full_url, options).then(data => {
                return data; // Successfully loaded the tile data
            }).catch(error => {
                console.error('Failed to load tile:', error);
                // Handle the error, e.g., return a fallback value or null
                return null;
            });
        },

        renderSubLayers: props => {
            const {
                bbox: {left, bottom, right, top}
            } = props.tile;
            const {width, height} = dimensions;

            // return new BitmapLayer(props, {
            return new CustomBitmapLayer(props, {
                data: null,
                image: props.data,
                bounds: [
                    mathGl.clamp(left, 0, width),
                    mathGl.clamp(bottom, 0, height),
                    mathGl.clamp(right, 0, width),
                    mathGl.clamp(top, 0, height)
                ],
                color: [255, 0, 0], // Custom color
                opacityScale: 3.0, // Custom opacity scale
            });
        },
    });

    const image_name_2 = 'dapi'

    const tile_layer_2 = new TileLayer({
        id: 'tile_layer_2',
        tileSize: dimensions.tileSize,
        refinementStrategy: 'no-overlap',
        minZoom: -7,
        maxZoom: 0,
        maxCacheSize: 20, // 5
        extent: [0, 0, dimensions.width, dimensions.height],
        getTileData: ({index}) => {
            const {x, y, z} = index;
            const full_url = `${base_url}/pyramid_images/${image_name_2}.image_files/${max_image_zoom + z}/${x}_${y}.jpeg`;

            return load(full_url, options).then(data => {
                return data; // Successfully loaded the tile data
            }).catch(error => {
                console.error('Failed to load tile:', error);
                // Handle the error, e.g., return a fallback value or null
                return null;
            });
        },

        renderSubLayers: props => {
            const {
                bbox: {left, bottom, right, top}
            } = props.tile;
            const {width, height} = dimensions;

            return new BitmapLayer(props, {
            // return new CustomBitmapLayer(props, {
                data: null,
                image: props.data,
                bounds: [
                    mathGl.clamp(left, 0, width),
                    mathGl.clamp(bottom, 0, height),
                    mathGl.clamp(right, 0, width),
                    mathGl.clamp(top, 0, height)
                ]
            });
        },
    });

    //////////////////////////////////////////
    // Cell/Trx Code
    //////////////////////////////////////////

    const tileSize = 1000;
    const max_tiles_to_view = 15

    const debounced_calc_viewport = debounce(calc_viewport, bounce_time);

    const cell_url = base_url + `/real_cells_mosaic.parquet`;
    var cell_arrow_table = await get_arrow_table(cell_url, options.fetch)

    var cell_scatter_data = get_scatter_data(cell_arrow_table)

    const meta_gene_url = base_url + `/meta_gene.parquet`;
    var meta_gene = await get_arrow_table(meta_gene_url, options.fetch)

    let geneNames = [];
    let colors = [];

    // Assuming 'cell_arrow_table' is your ArrowTable
    // And it has columns named '__index_level_0__' for gene names and 'color' for colors
    const geneNameColumn = meta_gene.getChild('__index_level_0__');
    const colorColumn = meta_gene.getChild('color');

    if (geneNameColumn && colorColumn) {
        // If the table is large, consider a more efficient way to handle data extraction
        geneNames = geneNameColumn.toArray();
        colors = colorColumn.toArray();
    }

    let color_dict = {};

    geneNames.forEach((geneName, index) => {
        color_dict[geneName] = hexToRgb(colors[index]);
    });

    const cell_names_array = cell_arrow_table.getChild("name").toArray();


    const cell_layer = new ScatterplotLayer({
        id: 'cell-layer',
        data: cell_scatter_data,
        getRadius: 5.0,
        pickable: true,
        getColor: [0, 0, 255, 240],
        onClick: info => {
          console.log('click!!')
          console.log(info.index)
          console.log(cell_names_array[info.index])
        },
    });

    // mutable transcript data is initialized as an empty array
    var trx_data = []

    const trx_layer = new ScatterplotLayer({
        id: 'trx-layer',
        data: trx_data,
        getRadius: 0.5,
        pickable: true,
        // getColor: [200, 0, 0, 150],
        getColor: (i, d) => {
          var inst_gene = trx_names_array[d.index]
          var inst_color = color_dict[inst_gene]
          return [inst_color[0], inst_color[1], inst_color[2], 255]
        },

    });

	// console.log('creating polygonlayer')
    const polygon_layer = new PathLayer({
      id: 'path_layer',
      data: [],
      pickable: true,
      widthScale: 3,
      widthMinPixels: 1,
      getPath: d => d,
      getColor: [255, 255, 255, 150], // white outline
      widthUnits: 'pixels',
    })

    // Create and append the visualization.
    let root = document.createElement("div");
    root.style.height = "800px";
    let deck = new Deck({
        parent: root,
        controller: {doubleClickZoom: false},
        initialViewState: {target: [ini_x, ini_y, 0], zoom: ini_zoom},
        views: [new OrthographicView({id: 'ortho'})],

        layers: [tile_layer_2, tile_layer, cell_layer],
        // layers: [tile_layer, cell_layer],

        onViewStateChange: ({viewState}) => {
          debounced_calc_viewport(viewState, options)
          return viewState
        },
        getTooltip: make_tooltip,
    });
    el.appendChild(root);

	// console.log('returning deck')

    return () => deck.finalize();

}

export default { render };
