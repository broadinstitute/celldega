import * as d3 from 'd3';

import { create_enrich_store } from '../obs_store/enrich_store';
import { postGeneList, fetchEnrichment } from '../external_apis/enrichr_api';
import { handleAsyncError } from '../temp_utils/errorHandler';
import { updateParagraphColors, updateGeneInfo } from '../widget_interactions/enrich_utils';
import { sync_selected_genes } from '../global_variables/selected_genes';

// Add enrichment controls to the clustergram view. This closely mirrors the
// behaviour of the standalone enrichment widget but mounts the UI inside the
// clustergram container and wires it to the clustergram observables.
export const add_enrich_to_clustergram = (viz_state) => {
  const store = create_enrich_store();

  // populate enrichment libraries and default selection
  store.available_libs.set([
    'CellMarker_2024',
    'ARCHS4_Tissues',
    'GO_Biological_Process_2025',
    'GO_Cellular_Component_2025',
    'GO_Molecular_Function_2025',
    'GTEx_Tissue_Expression_Up',
    'KEGG_2019_Human',
    'ChEA_2022',
    'MGI_Mammalian_Phenotype_Level_4_2024',
    'Disease_Perturbations_from_GEO_up',
    'Ligand_Perturbations_from_GEO_up',
    'LINCS_L1000_Chem_Pert_down',
    'Ligand_Perturbations_from_GEO_down',
  ]);

  const container = document.createElement('div');
  container.style.marginTop = '10px';
  container.style.width = '100%';

  const select = document.createElement('select');
  select.style.marginBottom = '5px';
  container.appendChild(select);

  const barHolder = document.createElement('div');
  barHolder.style.width = '100%';
  barHolder.style.maxHeight = '250px';
  barHolder.style.overflowY = 'auto';
  barHolder.style.border = '1px solid #d3d3d3';
  container.appendChild(barHolder);

  const geneListHolder = document.createElement('div');
  geneListHolder.style.marginTop = '5px';
  geneListHolder.style.maxHeight = '120px';
  geneListHolder.style.overflowY = 'auto';
  geneListHolder.style.border = '1px solid #d3d3d3';
  container.appendChild(geneListHolder);

  const geneInfoHolder = document.createElement('div');
  geneInfoHolder.style.marginTop = '5px';
  geneInfoHolder.style.maxHeight = '120px';
  geneInfoHolder.style.overflowY = 'auto';
  geneInfoHolder.style.border = '1px solid #d3d3d3';
  geneInfoHolder.style.fontFamily =
    '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';
  container.appendChild(geneInfoHolder);

  // dropdown options
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
  store.selected_lib.subscribe(() => {
    select.value = store.selected_lib.get();
  }, { immediate: false });
  select.addEventListener('change', (e) => {
    store.selected_lib.set(e.target.value);
  });

  let paragraphElement = null;

  // gene info interactions
  store.term_genes.subscribe((tg) => {
    updateParagraphColors(paragraphElement, tg);
  }, { immediate: false });
  store.gene_of_interest.subscribe((gene) => {
    updateGeneInfo(gene, geneInfoHolder);
  }, { immediate: false });

  const cache = {};

  const update = async () => {
    const genes = viz_state.obs_store.selected_genes.get();
    const lib = store.selected_lib.get();
    const numTerms = viz_state.top_n_genes || 10;
    if (!genes || genes.length === 0) {
      barHolder.textContent = 'No genes selected.';
      geneListHolder.textContent = '';
      return;
    }
    barHolder.textContent = 'Loading...';

    try {
      const cacheKey = `${genes.join(',')}__${lib}`;
      let data; let shortId;
      if (cache[cacheKey]) {
        ({ data, shortId } = cache[cacheKey]);
      } else {
        const { userListId, shortId: sId } = await postGeneList(genes);
        shortId = sId;
        data = await fetchEnrichment(userListId, lib);
        cache[cacheKey] = { data, shortId };
      }
      const bar_data = (data[lib] || [])
        .map((d) => ({ name: d[1], score: d[4], genes: d[5] }))
        .sort((a, b) => b.score - a.score)
        .slice(0, numTerms);
      const bar_values = bar_data.map((x) => x.score);
      const width = barHolder.clientWidth || 350;
      const xScale = d3
        .scaleLinear()
        .domain([0, bar_values.length > 0 ? d3.max(bar_values) : 0])
        .range([0, width - 5]);
      const yScale = d3
        .scaleBand()
        .domain(d3.range(bar_values.length))
        .range([0, 22 * bar_values.length]);
      const svg = d3
        .create('svg')
        .attr('width', width)
        .attr('height', yScale.range()[1])
        .style('font-family', '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif')
        .attr('font-size', '14')
        .attr('text-anchor', 'end');
      const defaultValue = { term_name: 'Select Term', term_genes: [], score: 0 };
      svg.property('value', { ...defaultValue });
      const bar = svg
        .selectAll('g')
        .data(bar_data)
        .join('g')
        .attr('transform', (d, i) => `translate(0,${yScale(i)})`)
        .on('click', function (_event, d) {
          const isSelected = store.selected_term.get() === d.name;
          const value_dict = isSelected ? defaultValue : {
            term_genes: d.genes.map((x) => x.toLowerCase()),
            term_name: d.name,
            score: d.score,
          };
          svg.property('value', value_dict).dispatch('input');
          if (!isSelected) {
            svg.selectAll('text').attr('fill', 'gray');
            d3.select(this).select('text').attr('fill', 'black');
          } else {
            svg.selectAll('text').attr('fill', 'black');
          }
        });
      bar
        .append('rect')
        .attr('fill', 'steelblue')
        .attr('opacity', 0.25)
        .attr('width', (d) => xScale(d.score))
        .attr('height', yScale.bandwidth() - 1);
      bar
        .append('text')
        .attr('fill', 'black')
        .attr('x', '5px')
        .attr('y', yScale.bandwidth() / 2)
        .attr('dy', '0.35em')
        .attr('text-anchor', 'start')
        .text((d) => d.name);
      const new_chart = svg.node();
      barHolder.innerHTML = '';
      barHolder.appendChild(new_chart);

      paragraphElement = document.createElement('div');
      paragraphElement.style.userSelect = 'none';
      paragraphElement.value = 'Click on a gene to obtain detailed information';
      d3.select(paragraphElement)
        .selectAll('div')
        .data(genes.map((x) => `${x}, `))
        .join('span')
        .text((d) => d)
        .style('font-weight', '550')
        .style('font-family', '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif')
        .style('color', () => 'black')
        .on('click', function (_event, d) {
          const gene = d.replace(', ', '');
          const current = store.gene_of_interest.get();
          if (gene === current) {
            store.gene_of_interest.set('');
            paragraphElement.value = 'Click on a gene to obtain detailed information';
            d3.select(paragraphElement).selectAll('span').style('font-weight', '550');
          } else {
            d3.select(paragraphElement).selectAll('span').style('font-weight', '550');
            d3.select(this).style('font-weight', 'bold');
            store.gene_of_interest.set(gene);
            paragraphElement.value = gene;
          }
          paragraphElement.dispatchEvent(new CustomEvent('input'));
        });
      geneListHolder.innerHTML = '';
      geneListHolder.appendChild(paragraphElement);

      new_chart.addEventListener('input', () => {
        const val = new_chart.value || {};
        store.term_genes.set(val.term_genes || []);
        store.selected_term.set(val.term_name);
        updateParagraphColors(paragraphElement, store.term_genes.get());
        if (val.term_genes && val.term_genes.length > 0) {
          // highlight genes in clustergram by syncing selected genes
          sync_selected_genes(viz_state, val.term_genes);
        }
      });
      updateParagraphColors(paragraphElement, store.term_genes.get());
    } catch (error) {
      handleAsyncError(error, { context: 'add_enrich_to_clustergram' });
      barHolder.textContent = 'Error loading enrichment data.';
      geneListHolder.textContent = '';
    }
  };

  viz_state.obs_store.selected_genes.subscribe(update, { immediate: true });
  store.selected_lib.subscribe(update, { immediate: false });

  return container;
};
