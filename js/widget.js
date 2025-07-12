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
import { fetchRefSeqInfo } from './external_apis/refseq_api';
import { create_enrich_store } from './obs_store/enrich_store';
import { updateParagraphColors, updateGeneInfo } from './widget_interactions/enrich_utils';
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
  // let network = model.get('network');
  let network;
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

  return matrix_viz(model, el, network, width, height);
};

const render_enrich = async ({ model, el }) => {
  const store = create_enrich_store();
  store.available_libs.set(model.get('available_libs') || []);
  store.selected_lib.set(model.get('inst_lib') || 'KEGG_2019_Human');

  const cache = {};
  let paragraphElement = null;

  const container = document.createElement('div');
  const select = document.createElement('select');
  const layout = document.createElement('div');
  const barHolder = document.createElement('div');
  const infoHolder = document.createElement('div');
  const geneInfoHolder = document.createElement('div');
  const paragraphHolder = document.createElement('div');

  container.appendChild(select);
  container.appendChild(layout);
  layout.appendChild(barHolder);
  layout.appendChild(infoHolder);
  infoHolder.appendChild(paragraphHolder);
  infoHolder.appendChild(geneInfoHolder);
  el.appendChild(container);

  container.style.width = '800px';
  layout.style.display = 'flex';
  layout.style.width = '800px';
  layout.style.height = '500px';
  barHolder.style.width = '250px';
  barHolder.style.height = '100%';
  barHolder.style.overflowY = 'auto';
  infoHolder.style.width = '550px';
  infoHolder.style.height = '100%';
  infoHolder.style.overflowY = 'auto';
  paragraphHolder.style.height = '60%';
  paragraphHolder.style.overflowY = 'auto';
  geneInfoHolder.style.marginTop = '10px';

  paragraphHolder.textContent = 'Paragraph view';
  geneInfoHolder.textContent = 'Gene info';

  const updateSelectOptions = () => {
    select.innerHTML = '';
    store.available_libs.get().forEach((lib) => {
      const opt = document.createElement('option');
      opt.value = lib;
      opt.textContent = lib;
      select.appendChild(opt);
    });
    select.value = store.selected_lib.get();
  };

  store.available_libs.subscribe(updateSelectOptions);
  store.selected_lib.subscribe(
    () => {
      select.value = store.selected_lib.get();
    },
    { immediate: false }
  );

  select.addEventListener('change', (e) => {
    store.selected_lib.set(e.target.value);
    model.set('inst_lib', e.target.value);
    model.save_changes();
  });

  model.on('change:available_libs', () => {
    store.available_libs.set(model.get('available_libs') || []);
  });
  model.on('change:inst_lib', () => {
    store.selected_lib.set(model.get('inst_lib'));
  });


  store.term_genes.subscribe(
    (tg) => {
      updateParagraphColors(paragraphElement, tg);
    },
    { immediate: false }
  );
  store.gene_of_interest.subscribe(
    (gene) => updateGeneInfo(gene, geneInfoHolder),
    { immediate: false }
  );

  const update = async () => {
    const genes = model.get('gene_list') || [];
    const lib = store.selected_lib.get();
    const numTerms = model.get('num_terms') || 10;

    if (genes.length === 0) {
      barHolder.textContent = 'No genes provided.';
      geneInfoHolder.textContent = '';
      return;
    }

    barHolder.textContent = 'Loading...';

    try {
      const cacheKey = `${genes.join(',')}__${lib}`;
      let data;
      if (cache[cacheKey]) {
        data = cache[cacheKey];
      } else {
        const listId = await postGeneList(genes);
        data = await fetchEnrichment(listId, lib);
        cache[cacheKey] = data;
      }

      console.log(data);
      const bar_data = (data[lib] || [])
        .map((d) => ({ name: d[1], score: d[4], genes: d[5] }))
        .sort((a, b) => b.score - a.score)
        .slice(0, numTerms);

      console.log('bar_data:', bar_data);

      const bar_data_values = bar_data.map((x) => x.score);

      const width = 250;

      const table = document.createElement('table');

      const x_new = d3
        .scaleLinear()
        .domain([0, d3.max(bar_data_values)])
        .range([0, width]);

      const y_new = d3
        .scaleBand()
        .domain(d3.range(bar_data_values.length))
        .range([0, 22 * bar_data_values.length]);

      const svg = d3
        .create('svg')
        .attr('width', width)
        .attr('height', y_new.range()[1])
        .attr('font-family', 'sans-serif')
        .attr('font-size', '16')
        .attr('text-anchor', 'end');

      const default_value = {
        term_name: 'Select Term',
        term_genes: [],
        score: 0,
      };

      // initialized
      svg.property('value', { ...default_value });

      const bar = svg
        .selectAll('g')
        .data(bar_data)
        .join('g')
        .attr('transform', (d, i) => `translate(0,${y_new(i)})`)
        .on('click', function (event, d) {
          const isSelected = store.selected_term.get() === d.name;

          const value_dict = isSelected
            ? default_value
            : {
                term_genes: d.genes.map((x) => x.toLowerCase()),
                term_name: d.name,
                score: d.score,
              };

          svg.property('value', value_dict).dispatch('input');

          svg.selectAll('g').attr('font-weight', 'normal');
          svg.selectAll('text').attr('fill', isSelected ? 'black' : 'lightgray');

          if (!isSelected) {
            d3.select(this).attr('font-weight', 'bold');
            d3.select(this).select('text').attr('fill', 'black');
          }
        });

      bar
        .append('rect')
        .attr('fill', 'steelblue')
        .attr('opacity', 0.25)
        // .attr("width", function(d){return x_new(d.value)})
        .attr('width', function (d) {
          let inst_width = x_new(d.score);
          console.log('inst_width:', inst_width, 'score:', d.score);
          return inst_width;
        })
        .attr('height', y_new.bandwidth() - 1);

      bar
        .append('text')
        .attr('fill', 'black')
        //.attr("x", d => x_new(d.value) - 3)
        .attr('x', '5px')
        .attr('y', y_new.bandwidth() / 2)
        .attr('dy', '0.35em')
        .attr('text-anchor', 'start')
        .text((d) => d.name);

      const new_chart = svg.node();

      barHolder.innerHTML = '';
      // barHolder.appendChild(table);

      // Paragraph visual
      //////////////////////////////////////////////////

      const element = document.createElement('div');
      element.style.display = 'inline-block';
      element.style.userSelect = 'none';

      paragraphElement = element;

      d3.select(element).append('h3').text(new_chart.term_name);
      d3.select(element)
        .append('h5')
        .text('Combined Score ' + new_chart.score);

      element.value = 'Click on a gene to obtain detailed information';

      d3.select(element)
        .selectAll('div')
        .data(genes.map((x) => x + ', '))
        .join('span')
        .text((d) => d)
        .style('font-weight', '550')
        .style('color', () => 'black')
        .on('click', function (event, d) {
          const gene = d.replace(', ', '');
          const current = store.gene_of_interest.get();

          if (gene === current) {
            // Toggle off if clicking the same gene
            store.gene_of_interest.set('');
            element.value = 'Click on a gene to obtain detailed information';
            d3.select(element).selectAll('span').style('font-weight', '550');
          } else {
            d3.select(element).selectAll('span').style('font-weight', '550');
            d3.select(this).style('font-weight', 'bold');
            store.gene_of_interest.set(gene);
            element.value = gene;
          }

          element.dispatchEvent(new CustomEvent('input'));
        });

      barHolder.appendChild(new_chart);
      paragraphHolder.innerHTML = '';
      paragraphHolder.appendChild(element);

      new_chart.addEventListener('input', () => {
        const val = new_chart.value || {};
        store.term_genes.set(val.term_genes || []);
        store.selected_term.set(val.term_name);
        d3.select(element).select('h3').text(val.term_name);
        d3.select(element)
          .select('h5')
          .text('Combined Score ' + val.score);
        updateParagraphColors(element, store.term_genes.get());
      });

      updateParagraphColors(element, store.term_genes.get());
    } catch (error) {
      handleAsyncError(error, { context: 'render_enrich' });
      barHolder.textContent = 'Error loading enrichment data.';
      geneInfoHolder.textContent = '';
    }
  };

  model.on('change:gene_list', update);
  model.on('change:inst_lib', update);
  model.on('change:num_terms', update);
  await update();
};

// Main render function - no export keyword
async function render({ model, el }) {
  let cleanup = null;
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
        cleanup = await render_landscape({ model, el });
        break;
      case 'Matrix':
        // return render_matrix_new({ model, el });
        cleanup = await render_matrix_new({ model, el });
        break;
      case 'Enrich':
        return render_enrich({ model, el });
      default:
        handleValidationWarning(`Unknown component type: ${componentType}`, {
          data: { componentType, model: model?.id || 'unknown' },
        });
        return;
    }

    model.on('msg:custom', (msg) => {
      if (msg.event === 'finalize' && cleanup) {
        try {
          if (typeof cleanup === 'function') {
            cleanup();
          } else if (cleanup.finalize) {
            cleanup.finalize();
          }
        } catch (e) {
          // do not use console.log in production code
          handleValidationWarning('Error finalizing deck', {
            data: { error: e.message, model: model?.id || 'unknown' },
          });
        }
        cleanup = null;
      }
    });
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
