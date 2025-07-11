import './widget.css';
import { networkFromParquet } from './read_parquet/network_from_parquet';
import {
  handleAsyncError,
  handleValidationWarning,
} from './temp_utils/errorHandler';
import { landscape_h_e } from './viz/landscape_h_e';
import { landscape_ist } from './viz/landscape_ist';
import { landscape_sst } from './viz/landscape_sst';
import { matrix_viz } from './viz/matrix_viz';
import { postGeneList, fetchEnrichment } from './external_apis/enrichr_api';
import { uniprot_data, uniprot_get_request } from './external_apis/uniprot_api';
import { fetchRefSeqInfo } from './external_apis/refseq_api';
import * as d3 from 'd3';

// Remove export keywords from render functions
const render_landscape_ist = async ({ model, el }) => {
  const token = model.get('token');
  const creds = model.get('creds');
  const ini_x = model.get('ini_x');
  const ini_y = model.get('ini_y');
  const ini_z = model.get('ini_z');
  const ini_zoom = model.get('ini_zoom');
  const base_url = model.get('base_url');
  const dataset_name = model.get('dataset_name');
  const width = model.get('width');
  const height = model.get('height');
  const meta_cell = model.get('meta_cell');
  const meta_cluster = model.get('meta_cluster');
  const umap = model.get('umap');
  const landscape_state = model.get('landscape_state');
  const segmentation = model.get('segmentation');

  return landscape_ist(
    el,
    model,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    base_url,
    dataset_name,
    0.25,
    width,
    height,
    meta_cell,
    meta_cluster,
    umap,
    landscape_state,
    segmentation,
    creds
  );
};

const render_landscape_sst = async ({ model, el }) => {
  const token = model.get('token');
  const ini_x = model.get('ini_x');
  const ini_y = model.get('ini_y');
  const ini_z = model.get('ini_z');
  const ini_zoom = model.get('ini_zoom');
  const base_url = model.get('base_url');
  const dataset_name = model.get('dataset_name');
  const square_tile_size = model.get('square_tile_size');
  const width = model.get('width');
  const height = model.get('height');

  landscape_sst(
    model,
    el,
    base_url,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    square_tile_size,
    dataset_name,
    width,
    height
  );
};

const render_landscape_h_e = async ({ model, el }) => {
  const token = model.get('token');
  const ini_x = model.get('ini_x');
  const ini_y = model.get('ini_y');
  const ini_z = model.get('ini_z');
  const ini_zoom = model.get('ini_zoom');
  const base_url = model.get('base_url');
  const dataset_name = model.get('dataset_name');
  const width = model.get('width');
  const height = model.get('height');
  const creds = model.get('creds');

  landscape_h_e(
    model,
    el,
    base_url,
    token,
    ini_x,
    ini_y,
    ini_z,
    ini_zoom,
    dataset_name,
    width,
    height,
    creds
  );
};

const render_landscape = async ({ model, el }) => {
  const technology = model.get('technology');

  if (['MERSCOPE', 'Xenium'].includes(technology)) {
    return render_landscape_ist({ model, el });
  } else if (['Visium-HD'].includes(technology)) {
    return render_landscape_sst({ model, el });
  } else if (['h&e'].includes(technology)) {
    return render_landscape_h_e({ model, el });
  }
};

const render_matrix_new = async ({ model, el }) => {
  let network = model.get('network');
  const width = model.get('width');
  const height = model.get('height');

  const matBytes = model.get('mat_parquet');
  if (matBytes && matBytes.byteLength > 0) {
    network = await networkFromParquet(
      model.get('network_meta'),
      matBytes,
      model.get('row_nodes_parquet'),
      model.get('col_nodes_parquet'),
      model.get('row_linkage_parquet'),
      model.get('col_linkage_parquet')
    );
  }

  matrix_viz(model, el, network, width, height);
};

const render_enrich = async ({ model, el }) => {
  const container = document.createElement('div');
  const tableHolder = document.createElement('div');
  const geneInfoHolder = document.createElement('div');
  container.appendChild(tableHolder);
  container.appendChild(geneInfoHolder);
  el.appendChild(container);

  const update = async () => {
    const genes = model.get('gene_list') || [];
    const lib = model.get('inst_lib') || 'KEGG_2019_Human';
    const numTerms = model.get('num_terms') || 10;

    if (genes.length === 0) {
      tableHolder.textContent = 'No genes provided.';
      geneInfoHolder.textContent = '';
      return;
    }

    tableHolder.textContent = 'Loading...';

    try {
      const listId = await postGeneList(genes);
      const data = await fetchEnrichment(listId, lib);

      console.log(data)
      const bar_data = (data[lib] || [])
        .map((d) => ({ name: d[1], score: d[4], genes: d[5] }))
        .sort((a, b) => b.score - a.score)
        .slice(0, numTerms);

      console.log('bar_data:', bar_data);

      const term_list = bar_data.map(x => x.name)
      const score_list = bar_data.map(x => x.score)
      const bar_data_values = bar_data.map(x => x.score)

      const width = 250

      const table = document.createElement('table');

      const x_new = d3.scaleLinear()
          .domain([0, d3.max(bar_data_values)])
          .range([0, width])

      const y_new = d3.scaleBand()
          .domain(d3.range(bar_data_values.length))
          .range([0, 22 * bar_data_values.length])

      const svg = d3.create("svg")
          .attr("width", width)
          .attr("height", y_new.range()[1])
          .attr("font-family", "sans-serif")
          .attr("font-size", "16")
          .attr("text-anchor", "end");

      // initialized
      svg.property('value', {
        'term_name': 'Select Term',
        'term_genes': []
      })

      const bar = svg.selectAll("g")
        .data(bar_data)
        .join("g")
          .attr("transform", (d, i) => `translate(0,${y_new(i)})`)
          .on('click', function(event, d){

            console.log(d)
            // from https://twitter.com/darth_mall/status/961770045826371584?s=20
            let term_genes = d.genes.map(x => x.toLowerCase())
            let value_dict = {}
            value_dict.term_genes = term_genes
            value_dict.term_name = d.name
            value_dict.score = d.value

            svg.property("value", value_dict)
              .dispatch("input");

            svg.selectAll("g")
              .attr('font-weight', 'normal')

            d3.select(this)
              .attr('font-weight', 'bold')
          })

      bar.append("rect")
          .attr("fill", "steelblue")
          .attr('opacity', 0.25)
          // .attr("width", function(d){return x_new(d.value)})
          .attr("width", function(d){
            let inst_width = x_new(d.score);
            console.log('inst_width:', inst_width, 'score:', d.score);
            return inst_width
          })
          .attr("height", y_new.bandwidth() - 1);

      bar.append("text")
          .attr("fill", 'black')
          //.attr("x", d => x_new(d.value) - 3)
          .attr("x", '5px')
          .attr("y", y_new.bandwidth() / 2)
          .attr("dy", "0.35em")
          .attr('text-anchor', 'start')
          .text(d => d.name);

      tableHolder.innerHTML = '';
      // tableHolder.appendChild(table);
      tableHolder.appendChild(svg.node());


    } catch (error) {
      handleAsyncError(error, { context: 'render_enrich' });
      tableHolder.textContent = 'Error loading enrichment data.';
      geneInfoHolder.textContent = '';
    }
  };

  model.on('change:gene_list', update);
  model.on('change:inst_lib', update);
  model.on('change:num_terms', update);
  await update();
};

// Main render function - no export keyword
function render({ model, el }) {
  try {
    const componentType = model.get('component');

    // Add null/undefined checks
    if (!componentType) {
      handleValidationWarning('Component type is not defined', {
        data: { model: model?.id || 'unknown', el: el?.id || 'unknown' },
      });
      return;
    }

    switch (componentType) {
      case 'Landscape':
        return render_landscape({ model, el });
      case 'Matrix':
        return render_matrix_new({ model, el });
      case 'Enrich':
        return render_enrich({ model, el });
      default:
        handleValidationWarning(`Unknown component type: ${componentType}`, {
          data: { componentType, model: model?.id || 'unknown' },
        });
        return;
    }
  } catch (error) {
    const errorResult = handleAsyncError(error, {
      context: 'render function',
      logUnexpected: true,
      messages: {
        unexpected: 'Error in render function',
      },
    });

    // Create error display in the element
    el.innerHTML = `<div style="color: red; padding: 10px;">Error: ${errorResult.message}</div>`;
  }
}

export default {
  landscape_ist,
  landscape_sst,
  landscape_h_e,
  matrix_viz,
  render,
  render_landscape_ist,
  render_landscape_sst,
  render_landscape_h_e,
  render_landscape,
  render_matrix_new,
  render_enrich,
};
