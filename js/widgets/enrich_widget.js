import * as d3 from 'd3';

import { postGeneList, fetchEnrichment } from '../external_apis/enrichr_api';
import { create_enrich_store } from '../obs_store/enrich_store';
import { handleAsyncError } from '../temp_utils/errorHandler';
import {
  contain_scroll,
  escape_html,
  make_gene_hover_tooltip,
} from '../ui/gene_info';
import { make_logo_button } from '../ui/logo';
import {
  updateParagraphColors,
  updateGeneInfo,
} from '../widget_interactions/enrich_utils';

// Enrich typography lives in one stylesheet rather than per-element inline
// styles. Selectors are scoped under `.celldega-enrich` with enough
// specificity to win over host page rules (e.g. MkDocs `.md-typeset p`).
const ENRICH_FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

const enrich_style_block = `
.celldega-enrich {
  font-family: ${ENRICH_FONT_FAMILY};
  font-size: 12px;
  line-height: 1.35;
}
.celldega-enrich select,
.celldega-enrich .celldega-enrich__paragraph,
.celldega-enrich .celldega-enrich__paragraph *,
.celldega-enrich .celldega-enrich__gene-info,
.celldega-enrich .celldega-enrich__gene-info * {
  font-family: inherit;
  font-size: 12px;
  line-height: 1.35;
}
.celldega-enrich .celldega-enrich__paragraph,
.celldega-enrich .celldega-enrich__gene-info {
  padding: 3px;
}
.celldega-enrich .celldega-enrich__gene-info p {
  margin: 4px 0 0;
}
`;

let enrich_styles_injected = false;

const ensure_enrich_styles = () => {
  if (enrich_styles_injected || typeof document === 'undefined') return;
  const style_element = document.createElement('style');
  style_element.textContent = enrich_style_block;
  document.head.appendChild(style_element);
  enrich_styles_injected = true;
};

export const render_enrich = async ({ model, el }) => {
  const store = create_enrich_store();
  const subscriptions = [];
  store.available_libs.set(model.get('available_libs') || []);
  store.selected_lib.set(model.get('inst_lib') || 'CellMarker_2024');

  const cache = {};
  let paragraphElement = null;

  const highlightGeneSelection = (gene) => {
    if (!paragraphElement) return;

    const spans = paragraphElement.querySelectorAll('span');
    const normalized = (gene || '').toLowerCase();

    spans.forEach((span) => {
      const text = (span.textContent || '').replace(', ', '').toLowerCase();
      span.style.fontWeight =
        normalized && text === normalized ? 'bold' : '550';
    });

    paragraphElement.value = gene
      ? gene
      : 'Click on a gene to obtain detailed information';
  };

  const container = document.createElement('div');
  const header_row = document.createElement('div');
  const select = document.createElement('select');
  const layout = document.createElement('div');
  const barHolder = document.createElement('div');
  const infoHolder = document.createElement('div');
  // Transient hover info for genes in the paragraph view (the info panel
  // below stays stateful, changing only on click).
  const gene_hover_tooltip = make_gene_hover_tooltip();

  // Latest enrichment results, so a hovered gene can report which of the
  // shown terms it appears in.
  let current_terms = [];

  const format_p_value = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return null;
    return number < 0.001 ? number.toExponential(2) : number.toFixed(4);
  };

  /** Stats block for an enrichment term (hovering its bar). */
  const term_stats_html = (term) => {
    const lines = [
      `<span style="color: #7fb0ff;">${escape_html(term.name)}</span>`,
    ];

    if (Number.isFinite(Number(term.score))) {
      lines.push(`Combined score: ${Number(term.score).toFixed(1)}`);
    }
    const p_value = format_p_value(term.p_value);
    if (p_value) lines.push(`p-value: ${p_value}`);
    const adjusted_p = format_p_value(term.adjusted_p);
    if (adjusted_p) lines.push(`Adjusted p: ${adjusted_p}`);
    if (Number.isFinite(Number(term.odds_ratio))) {
      lines.push(`Odds ratio: ${Number(term.odds_ratio).toFixed(2)}`);
    }
    if (Array.isArray(term.genes)) {
      const count = term.genes.length;
      lines.push(`Overlap: ${count} gene${count === 1 ? '' : 's'}`);
    }

    return lines.join('<br>');
  };

  /** Where a hovered gene sits in the current enrichment results. */
  const gene_enrichment_html = (gene) => {
    if (!current_terms.length) return '';

    const target = String(gene).toUpperCase();
    const hits = current_terms.filter((term) =>
      (term.genes || []).some((name) => String(name).toUpperCase() === target)
    );

    if (!hits.length) {
      return `<br><i>Not in the ${current_terms.length} shown terms</i>`;
    }

    // current_terms is sorted by combined score, so hits[0] is the strongest.
    const best = hits[0];
    return `<br>In ${hits.length} of ${current_terms.length} shown terms<br>Top: ${escape_html(
      best.name
    )} (score ${Number(best.score).toFixed(1)})`;
  };

  const geneInfoHolder = document.createElement('div');
  const paragraphHolder = document.createElement('div');
  const sourceRow = document.createElement('div');
  const sourceText = document.createElement('span');
  const clearButton = document.createElement('button');
  const linkHolder = document.createElement('a');

  ensure_enrich_styles();
  container.className = 'celldega-enrich';
  paragraphHolder.className = 'celldega-enrich__paragraph';
  geneInfoHolder.className = 'celldega-enrich__gene-info';

  header_row.style.display = 'flex';
  header_row.style.flexDirection = 'row';
  header_row.style.alignItems = 'center';
  header_row.style.justifyContent = 'space-between';

  header_row.appendChild(select);
  header_row.appendChild(make_logo_button('enrich'));

  container.appendChild(header_row);
  container.appendChild(layout);
  sourceRow.appendChild(sourceText);
  sourceRow.appendChild(clearButton);
  container.appendChild(sourceRow);
  container.appendChild(linkHolder);
  layout.appendChild(barHolder);
  layout.appendChild(infoHolder);
  infoHolder.appendChild(paragraphHolder);
  infoHolder.appendChild(geneInfoHolder);
  el.appendChild(container);

  // One handler for the whole widget: the bar graph, paragraph view, gene info
  // panel, and the gaps between them all keep their wheel gestures to
  // themselves — including in the empty "no results" state, where none of
  // those panels has anything to scroll.
  contain_scroll(container);

  // get width/height from traitlets
  const width = (model.get('width') || 350) - 5;
  const height = model.get('height') || 500;

  container.style.width = `${width}px`;
  container.style.height = `${height}px`;
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.overflowX = 'scroll';
  container.style.marginLeft = '5px';

  select.style.marginTop = '5px';
  select.style.minWidth = '0';
  select.style.flex = '1 1 auto';

  layout.style.width = `${width}px`;
  // Reserve room at the bottom of the widget for the Enrichr link. Previously
  // this area consumed the full widget height, which pushed the link below the
  // visible Enrich pane.
  layout.style.flex = '1 1 auto';
  layout.style.minHeight = '0';
  layout.style.display = 'flex';
  layout.style.flexDirection = 'column';
  layout.style.gap = '5px';

  barHolder.style.width = `${width}px`;
  barHolder.style.height = 'auto';
  barHolder.style.flex = '0 0 45%';
  barHolder.style.minHeight = '0';
  barHolder.style.overflowY = 'auto';
  barHolder.style.border = '1px solid #d3d3d3';
  barHolder.style.userSelect = 'none';
  barHolder.style.webkitUserSelect = 'none';
  barHolder.style.cursor = 'pointer';

  infoHolder.style.width = `${width}px`;
  infoHolder.style.height = 'auto';
  infoHolder.style.flex = '1 1 0';
  infoHolder.style.minHeight = '0';
  infoHolder.style.display = 'flex';
  infoHolder.style.flexDirection = 'column';
  infoHolder.style.gap = '5px';

  paragraphHolder.style.height = 'auto';
  paragraphHolder.style.flex = '3 1 0';
  paragraphHolder.style.minHeight = '0';
  paragraphHolder.style.width = `${width}px`;
  paragraphHolder.style.marginTop = '0';
  paragraphHolder.style.overflowY = 'auto';
  paragraphHolder.style.border = '1px solid #d3d3d3';

  geneInfoHolder.style.height = 'auto';
  geneInfoHolder.style.flex = '2 1 0';
  geneInfoHolder.style.minHeight = '0';
  geneInfoHolder.style.width = `${width}px`;
  geneInfoHolder.style.marginTop = '0';
  geneInfoHolder.style.overflowY = 'auto';
  geneInfoHolder.style.border = '1px solid #d3d3d3';

  sourceRow.style.display = 'flex';
  sourceRow.style.alignItems = 'center';
  sourceRow.style.justifyContent = 'space-between';
  sourceRow.style.gap = '8px';
  sourceRow.style.width = `${width}px`;
  sourceRow.style.marginTop = '4px';
  sourceRow.style.fontSize = '11px';
  sourceRow.style.color = '#47515b';

  sourceText.style.overflow = 'hidden';
  sourceText.style.textOverflow = 'ellipsis';
  sourceText.style.whiteSpace = 'nowrap';

  clearButton.textContent = 'CLEAR';
  clearButton.title = 'Clear enrichment results';
  clearButton.setAttribute('aria-label', 'Clear enrichment results');
  clearButton.style.flex = '0 0 auto';
  clearButton.style.padding = '0';
  clearButton.style.border = '0';
  clearButton.style.background = 'transparent';
  clearButton.style.fontSize = '10px';
  clearButton.style.fontWeight = '700';
  clearButton.style.color = '#2f74ff';
  clearButton.style.cursor = 'pointer';

  linkHolder.style.display = 'block';
  linkHolder.style.flex = '0 0 auto';
  linkHolder.style.marginTop = '5px';
  linkHolder.style.color = '#47515b';
  linkHolder.target = '_blank';
  linkHolder.textContent = '';

  paragraphHolder.textContent = 'Paragraph view';
  geneInfoHolder.textContent = 'Gene info';

  const updateSourceRow = () => {
    const genes = model.get('gene_list') || [];
    const source = model.get('source_label') || 'Manual gene list';
    const geneCount = `${genes.length} gene${genes.length === 1 ? '' : 's'}`;

    sourceText.textContent = genes.length
      ? `Source: ${source} · ${geneCount}`
      : 'Source: No genes selected';
    clearButton.disabled = !genes.length;
    clearButton.style.color = genes.length ? '#2f74ff' : '#b8bec5';
    clearButton.style.cursor = genes.length ? 'pointer' : 'default';
  };

  const clearTermSelection = () => {
    store.term_genes.set([]);
    store.selected_term.set('Select Term');

    const currentGenes = model.get('term_genes') || [];
    const currentTerm = model.get('selected_term') || 'Select Term';
    if (!currentGenes.length && currentTerm === 'Select Term') return false;

    model.set('term_genes', []);
    model.set('selected_term', 'Select Term');
    model.save_changes();
    return true;
  };

  const onClearClick = () => {
    if (!model.get('gene_list')?.length) return;

    store.gene_of_interest.set('');
    clearTermSelection();
    model.set('gene_list', []);
    model.set('source_label', '');
    model.set('focused_gene', '');
    model.save_changes();
  };
  clearButton.addEventListener('click', onClearClick);

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

  subscriptions.push(store.available_libs.subscribe(updateSelectOptions));
  subscriptions.push(
    store.selected_lib.subscribe(
      () => {
        select.value = store.selected_lib.get();
      },
      { immediate: false }
    )
  );

  const onSelectChange = (e) => {
    store.selected_lib.set(e.target.value);
    model.set('inst_lib', e.target.value);
    model.save_changes();
  };
  select.addEventListener('change', onSelectChange);

  const onAvailableLibsChange = () => {
    store.available_libs.set(model.get('available_libs') || []);
  };

  subscriptions.push(
    store.term_genes.subscribe(
      (tg) => {
        if (paragraphElement) {
          updateParagraphColors(paragraphElement, tg);
        }
      },
      { immediate: false }
    )
  );

  subscriptions.push(
    store.gene_of_interest.subscribe(
      (gene) => {
        updateGeneInfo(gene, geneInfoHolder);
        highlightGeneSelection(gene);
      },
      { immediate: false }
    )
  );

  let updateRevision = 0;
  const update = async () => {
    const revision = ++updateRevision;
    const genes = model.get('gene_list') || [];
    const lib = store.selected_lib.get();
    const numTerms = model.get('num_terms') || 10;
    const background = model.get('background_list') || null;

    updateSourceRow();

    if (!genes.length) {
      clearTermSelection();
      current_terms = [];
      barHolder.textContent = 'No genes provided.';
      paragraphHolder.textContent = 'Paragraph view';
      geneInfoHolder.textContent = '';
      linkHolder.textContent = '';
      linkHolder.removeAttribute('href');
      return;
    }

    barHolder.textContent = 'Loading...';

    try {
      const cacheKey = `${genes.join(',')}__${lib}__${
        background ? background.join(',') : 'none'
      }`;

      let data;
      let shortId;

      if (cache[cacheKey]) {
        ({ data, shortId } = cache[cacheKey]);
      } else {
        const { userListId, shortId: sId } = await postGeneList(
          genes,
          background
        );
        if (revision !== updateRevision) return;
        shortId = sId;
        data = await fetchEnrichment(userListId, lib);
        cache[cacheKey] = { data, shortId };
      }

      if (revision !== updateRevision) return;

      // Enrichr row layout: [rank, term, p-value, odds ratio, combined score,
      // overlapping genes, adjusted p-value, ...]. The stats beyond score and
      // genes drive the hover tooltips.
      const bar_data = (data[lib] || [])
        .map((d) => ({
          name: d[1],
          p_value: d[2],
          odds_ratio: d[3],
          score: d[4],
          genes: d[5],
          adjusted_p: d[6],
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, numTerms);

      current_terms = bar_data;

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
        .attr('text-anchor', 'end')
        .style('cursor', 'pointer')
        .style('user-select', 'none')
        .style('-webkit-user-select', 'none');

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
        .style('cursor', 'pointer')
        .style('user-select', 'none')
        .style('-webkit-user-select', 'none')
        .on('pointerenter', function (event, d) {
          const barGroup = this;
          barGroup._enrichHoverTimer = setTimeout(() => {
            d3.select(barGroup).select('rect').attr('opacity', 0.45);
          }, 120);
          // Full term name plus its enrichment stats (the visible bar label
          // is usually clipped by the narrow panel).
          gene_hover_tooltip.show_html(term_stats_html(d), event);
        })
        .on('pointermove', (event) => gene_hover_tooltip.move(event))
        .on('pointerleave', function () {
          clearTimeout(this._enrichHoverTimer);
          this._enrichHoverTimer = null;
          d3.select(this).select('rect').attr('opacity', 0.25);
          gene_hover_tooltip.hide();
        })
        .on('click', function (_event, d) {
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
        .attr('width', (d) => x_new(d.score))
        .attr('height', y_new.bandwidth() - 1);

      bar
        .append('text')
        .attr('fill', 'black')
        .attr('x', '5px')
        .attr('y', y_new.bandwidth() / 2)
        .attr('dy', '0.35em')
        .attr('text-anchor', 'start')
        .style('cursor', 'pointer')
        .style('user-select', 'none')
        .style('-webkit-user-select', 'none')
        .text((d) => d.name);

      // (The complete term name now comes from the hover tooltip above, which
      // also carries the enrichment stats; a native <title> would double up.)

      const new_chart = svg.node();

      barHolder.innerHTML = '';

      const element = document.createElement('div');
      element.style.userSelect = 'none';
      element.style.webkitUserSelect = 'none';
      element.value = 'Click on a gene to obtain detailed information';

      paragraphElement = element;

      d3.select(element)
        .selectAll('div')
        .style('margin-top', '5px')
        .data(genes.map((x) => `${x}, `))
        .join('span')
        .text((d) => d)
        .style('font-weight', '550')
        .style('color', () => 'black')
        // Hovering a gene shows its UniProt name/description in a tooltip
        // (same lookup and shared cache the Clustergram/Landscape tooltips
        // use), leaving the clicked gene's info panel untouched.
        .on('mouseenter', (event, d) => {
          const gene = d.replace(', ', '');
          gene_hover_tooltip.show(gene, event, gene_enrichment_html(gene));
        })
        .on('mousemove', (event) => gene_hover_tooltip.move(event))
        .on('mouseleave', () => gene_hover_tooltip.hide())
        .on('click', function (_event, d) {
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
        const inst_genes = val.term_genes || [];
        const termName = val.term_name || 'Select Term';

        store.term_genes.set(inst_genes);
        store.selected_term.set(termName);
        model.set('term_genes', inst_genes);
        model.set('selected_term', termName);
        model.save_changes();

        updateParagraphColors(element, inst_genes);
      });

      updateParagraphColors(element, store.term_genes.get());

      if (shortId) {
        linkHolder.href = `https://maayanlab.cloud/Enrichr/enrich?dataset=${shortId}`;
        linkHolder.textContent = 'View full results on Enrichr';
      } else {
        linkHolder.textContent = '';
        linkHolder.removeAttribute('href');
      }
    } catch (error) {
      if (revision !== updateRevision) return;
      handleAsyncError(error, { context: 'render_enrich' });
      barHolder.textContent = 'Error loading enrichment data.';
      geneInfoHolder.textContent = '';
      linkHolder.textContent = '';
      linkHolder.removeAttribute('href');
    }
  };

  // Traitlet listeners
  const onInstLibChange = () => {
    store.selected_lib.set(model.get('inst_lib'));
    clearTermSelection();
    update();
  };
  const onGeneListChange = () => {
    clearTermSelection();
    update();
  };
  const onNumTermsChange = () => {
    clearTermSelection();
    update();
  };
  const onBackgroundListChange = () => {
    clearTermSelection();
    update();
  };
  const onFocusedGeneChange = () => {
    const gene = model.get('focused_gene') || '';
    if (store.gene_of_interest.get() !== gene) {
      store.gene_of_interest.set(gene);
    }
    highlightGeneSelection(gene);
  };
  const onTermGenesChange = () => {
    const incoming = model.get('term_genes') || [];
    store.term_genes.set(incoming);
    if (paragraphElement) {
      updateParagraphColors(paragraphElement, incoming);
    }
  };
  const onSelectedTermChange = () => {
    const nextTerm = model.get('selected_term') || 'Select Term';
    store.selected_term.set(nextTerm);
  };

  const traitListeners = [
    ['change:available_libs', onAvailableLibsChange],
    ['change:gene_list', onGeneListChange],
    ['change:source_label', updateSourceRow],
    ['change:inst_lib', onInstLibChange],
    ['change:num_terms', onNumTermsChange],
    ['change:background_list', onBackgroundListChange],
    ['change:focused_gene', onFocusedGeneChange],
    ['change:term_genes', onTermGenesChange],
    ['change:selected_term', onSelectedTermChange],
  ];

  traitListeners.forEach(([event, listener]) => model.on(event, listener));

  // Start the first request without delaying registration of the cleanup
  // callback. A widget finalized during a slow Enrichr request can then cancel
  // the remaining work and release its listeners immediately.
  update();

  return () => {
    // Invalidate any request already in flight before detaching the widget.
    updateRevision += 1;
    gene_hover_tooltip.hide();
    gene_hover_tooltip.destroy();
    subscriptions.forEach((unsubscribe) => unsubscribe?.());
    traitListeners.forEach(([event, listener]) => model.off?.(event, listener));
    clearButton.removeEventListener('click', onClearClick);
    select.removeEventListener('change', onSelectChange);
    container.remove();
  };
};
