import * as d3 from 'd3';

import { postGeneList, fetchEnrichment } from '../external_apis/enrichr_api';
import { create_enrich_store } from '../obs_store/enrich_store';
import { handleAsyncError } from '../temp_utils/errorHandler';
import {
  updateParagraphColors,
  updateGeneInfo,
} from '../widget_interactions/enrich_utils';

export const render_enrich = async ({ model, el }) => {
  const store = create_enrich_store();
  store.available_libs.set(model.get('available_libs') || []);
  store.selected_lib.set(model.get('inst_lib') || 'CellMarker_2024');

  const cache = {};
  let paragraphElement = null;

  const highlightGeneSelection = (gene) => {
    if (!paragraphElement) {
      return;
    }
    const spans = paragraphElement.querySelectorAll('span');
    const normalized = (gene || '').toLowerCase();
    spans.forEach((span) => {
      const text = (span.textContent || '').replace(', ', '').toLowerCase();
      span.style.fontWeight = normalized && text === normalized ? 'bold' : '550';
    });
    paragraphElement.value = gene
      ? gene
      : 'Click on a gene to obtain detailed information';
  };

  const container = document.createElement('div');
  const select = document.createElement('select');
  const layout = document.createElement('div');
  const barHolder = document.createElement('div');
  const infoHolder = document.createElement('div');
  const geneInfoHolder = document.createElement('div');
  const paragraphHolder = document.createElement('div');
  const linkHolder = document.createElement('a');

  container.appendChild(select);
  container.appendChild(layout);
  container.appendChild(linkHolder);
  layout.appendChild(barHolder);
  layout.appendChild(infoHolder);
  infoHolder.appendChild(paragraphHolder);
  infoHolder.appendChild(geneInfoHolder);
  el.appendChild(container);

  // const width = 350;
  // get width from traitlet
  const width = model.get('width') - 5 || 350;
  const height = model.get('height') || 500;

  container.style.width = `${width}px`;
  container.style.height = `${height}px`;
  container.overflowX = 'scroll';
  select.style.marginTop = '5px';
  container.style.marginLeft = '5px';

  select.style.width = `${width}px`;

  layout.style.width = `${width}px`;
  layout.style.height = `${height}px`;

  barHolder.style.width = `${width}px`;
  barHolder.style.height = '255px';
  barHolder.style.overflowY = 'auto';
  barHolder.style.border = '1px solid #d3d3d3';

  infoHolder.style.width = `${width}px`;
  infoHolder.style.height = '250px';

  paragraphHolder.style.height = '225px';
  paragraphHolder.style.width = `${width}px`;
  paragraphHolder.style.marginTop = '5px';
  paragraphHolder.style.overflowY = 'auto';
  paragraphHolder.style.border = '1px solid #d3d3d3';

  geneInfoHolder.style.height = '155px';
  geneInfoHolder.style.width = `${width}px`;
  geneInfoHolder.style.marginTop = '5px';
  geneInfoHolder.style.overflowY = 'auto';
  geneInfoHolder.style.border = '1px solid #d3d3d3';
  geneInfoHolder.style.fontFamily =
    '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

  linkHolder.style.display = 'block';
  linkHolder.style.marginTop = '5px';
  linkHolder.textContent = '';
  linkHolder.target = '_blank';

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
    (gene) => {
      updateGeneInfo(gene, geneInfoHolder);
      highlightGeneSelection(gene);
    },
    { immediate: false }
  );

  const update = async () => {
    const genes = model.get('gene_list') || [];
    const lib = store.selected_lib.get();
    const numTerms = model.get('num_terms') || 10;
    const background = model.get('background_list') || null;

    if (genes.length === 0) {
      barHolder.textContent = 'No genes provided.';
      geneInfoHolder.textContent = '';
      linkHolder.textContent = '';
      return;
    }

    barHolder.textContent = 'Loading...';

    try {
      const cacheKey = `${genes.join(',')}__${lib}__${background ? background.join(',') : 'none'}`;
      let data;
      let shortId;

      if (cache[cacheKey]) {
        ({ data, shortId } = cache[cacheKey]);
      } else {
        const { userListId, shortId: sId } = await postGeneList(
          genes,
          background
        );
        shortId = sId;
        data = await fetchEnrichment(userListId, lib);
        cache[cacheKey] = { data, shortId };
      }

      const bar_data = (data[lib] || [])
        .map((d) => ({ name: d[1], score: d[4], genes: d[5] }))
        .sort((a, b) => b.score - a.score)
        .slice(0, numTerms);

      const bar_data_values = bar_data.map((x) => x.score);

      const x_new = d3
        .scaleLinear()
        .domain([0, bar_data_values.length > 0 ? d3.max(bar_data_values) : 0])
        .range([0, width]);

      const y_new = d3
        .scaleBand()
        .domain(d3.range(bar_data_values.length))
        .range([0, 22 * bar_data_values.length]);

      const svg = d3
        .create('svg')
        .attr('width', width)
        .attr('height', y_new.range()[1])
        .style(
          'font-family',
          '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif'
        )
        .attr('font-size', '14')
        .attr('text-anchor', 'end');

      const default_value = {
        term_name: 'Select Term',
        term_genes: [],
        score: 0,
      };

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
        .attr('width', (d) => {
          const inst_width = x_new(d.score);
          return inst_width;
        })
        .attr('height', y_new.bandwidth() - 1);

      bar
        .append('text')
        .attr('fill', 'black')
        .attr('x', '5px')
        .attr('y', y_new.bandwidth() / 2)
        .attr('dy', '0.35em')
        .attr('text-anchor', 'start')
        .text((d) => d.name);

      const new_chart = svg.node();

      barHolder.innerHTML = '';

      const element = document.createElement('div');
      element.style.userSelect = 'none';

      paragraphElement = element;

      element.value = 'Click on a gene to obtain detailed information';

      d3.select(element)
        .selectAll('div')
        .style('margin-top', '5px')
        .data(genes.map((x) => `${x}, `))
        .join('span')
        .text((d) => d)
        .style('font-weight', '550')
        .style(
          'font-family',
          '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif'
        )
        .style('color', () => 'black')
        .on('click', function (event, d) {
          const gene = d.replace(', ', '');
          const current = store.gene_of_interest.get();

          if (gene === current) {
            store.gene_of_interest.set('');
            element.value = 'Click on a gene to obtain detailed information';
            d3.select(element).selectAll('span').style('font-weight', '550');
          } else {
            d3.select(element).selectAll('span').style('font-weight', '550');
            d3.select(this).style('font-weight', 'bold');
            store.gene_of_interest.set(gene);
            element.value = gene;
          }

          model.set('focused_gene', store.gene_of_interest.get() || '');
          model.save_changes();
          element.dispatchEvent(new CustomEvent('input'));
        });

      barHolder.appendChild(new_chart);
      paragraphHolder.innerHTML = '';
      paragraphHolder.appendChild(element);

      highlightGeneSelection(store.gene_of_interest.get());

      new_chart.addEventListener('input', () => {
        const val = new_chart.value || {};
        const genes = val.term_genes || [];
        const termName = val.term_name || 'Select Term';

        store.term_genes.set(genes);
        store.selected_term.set(termName);
        model.set('term_genes', genes);
        model.set('selected_term', termName);
        model.save_changes();

        updateParagraphColors(element, genes);
      });

      updateParagraphColors(element, store.term_genes.get());
      if (shortId) {
        linkHolder.href = `https://maayanlab.cloud/Enrichr/enrich?dataset=${shortId}`;
        linkHolder.textContent = 'View full results on Enrichr';
        linkHolder.target = '_blank';
        // make the text this color '#47515b'
        // linkHolder.textContent.style.color = '#47515b';
      } else {
        linkHolder.textContent = '';
      }
    } catch (error) {
      handleAsyncError(error, { context: 'render_enrich' });
      barHolder.textContent = 'Error loading enrichment data.';
      geneInfoHolder.textContent = '';
      linkHolder.textContent = '';
    }
  };

  model.on('change:gene_list', update);
  model.on('change:inst_lib', update);
  model.on('change:num_terms', update);
  model.on('change:background_list', update);
  model.on('change:focused_gene', () => {
    const gene = model.get('focused_gene') || '';
    if (store.gene_of_interest.get() !== gene) {
      store.gene_of_interest.set(gene);
    }
    highlightGeneSelection(gene);
  });
  model.on('change:term_genes', () => {
    const incoming = model.get('term_genes') || [];
    store.term_genes.set(incoming);
    updateParagraphColors(paragraphElement, incoming);
  });
  model.on('change:selected_term', () => {
    const nextTerm = model.get('selected_term') || 'Select Term';
    store.selected_term.set(nextTerm);
  });
  await update();
};
