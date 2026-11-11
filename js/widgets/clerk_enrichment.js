/**
 * Enrichr results drawn inside Clerk, like the Enrich panel: a library picker, a
 * scrolling bar graph of the top terms, a paragraph of the genes tested and a link to
 * the same results on the Enrichr website.
 *
 * Hovering a bar shows the term's statistics; clicking it colors the term's genes in
 * the paragraph (blue, the rest dark gray, as in Enrich) and shows them in the linked
 * views. Genes in the paragraph behave like Clerk's other gene links: hover for
 * UniProt, click to show. Picking a library Clerk didn't look up asks Enrichr from the
 * browser (`fetch_terms`).
 *
 * No imports: the panel passes everything in, so the module loads as is in tests.
 */

/** Libraries offered in the picker (the Enrich panel's defaults, plus cell types). */
export const ENRICHR_LIBRARIES = [
  'CellMarker_2024',
  'PanglaoDB_Augmented_2021',
  'Azimuth_Cell_Types_2021',
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
];

// Only links to the Enrichr site itself are shown.
const ENRICHR_PAGE =
  /^https:\/\/maayanlab\.cloud\/Enrichr\/enrich\?dataset=[A-Za-z0-9]+$/;

const format = (value, digits = 3) =>
  Number.isFinite(value) ? Number(value).toPrecision(digits) : '—';

/** A term's statistics, for the hover tooltip. */
export const term_html = (term, esc) =>
  [
    `<b>${esc(term.name)}</b>`,
    `Combined score ${format(term.score)}`,
    Number.isFinite(term.adjusted_p)
      ? `Adjusted p ${format(term.adjusted_p, 2)}`
      : '',
    Number.isFinite(term.odds_ratio)
      ? `Odds ratio ${format(term.odds_ratio)}`
      : '',
    term.genes?.length
      ? `Genes: ${esc(term.genes.slice(0, 12).join(', '))}${term.genes.length > 12 ? ', …' : ''}`
      : '',
  ]
    .filter(Boolean)
    .join('<br>');

/**
 * @param {{title?: string, label: string, genes: string[], url?: string,
 *   libraries: Object<string, Array<{name: string, score: number,
 *   adjusted_p?: number, odds_ratio?: number, genes: string[]}>>}} message - An
 *   `enrichment` message from Python.
 * @param {{on_gene: (gene: string, add: boolean) => void,
 *   on_genes: (genes: string[]) => void, tooltip: {show: Function,
 *   show_html: Function, move: Function, hide: Function},
 *   esc: (value: unknown) => string,
 *   fetch_terms?: (genes: string[], library: string) =>
 *     Promise<{terms: object[], url?: string}>,
 *   libraries?: string[], contain_scroll?: (el: HTMLElement) => void,
 *   show_title?: boolean}} handlers
 * @returns {HTMLElement}
 */
export const render_enrichment = (
  message,
  {
    on_gene,
    on_genes,
    tooltip,
    esc,
    fetch_terms = null,
    libraries: offered = ENRICHR_LIBRARIES,
    contain_scroll = null,
    show_title = true,
  }
) => {
  // Results per library: Clerk's own first, then any fetched here.
  const results = new Map(
    Object.entries(message.libraries || {}).filter(([, terms]) => terms?.length)
  );
  const genes = (message.genes || []).map(String);
  let url = ENRICHR_PAGE.test(message.url || '') ? message.url : '';

  const card = document.createElement('div');
  card.className = 'clerk-enrichment';

  if (show_title) {
    const title = document.createElement('div');
    title.className = 'clerk-enrichment-title';
    title.textContent = `Enrichr · ${message.title || message.label || 'genes'}`;
    card.appendChild(title);
  }

  const picker = document.createElement('select');
  picker.className = 'clerk-enrichment-library';
  picker.title = 'Enrichr library';
  const names = [
    ...new Set([...results.keys(), ...(fetch_terms ? offered : [])]),
  ];
  names.forEach((name) => {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    picker.appendChild(option);
  });
  const chart = document.createElement('div');
  chart.className = 'clerk-enrichment-bars';
  const paragraph = document.createElement('div');
  paragraph.className = 'clerk-enrichment-genes';
  const link = document.createElement('a');
  link.className = 'clerk-enrichment-link';
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  link.textContent = 'View full results on Enrichr';
  if (names.length > 1) card.appendChild(picker);
  card.append(chart, paragraph, link);
  // Scrolling the bars stops at their ends instead of scrolling the conversation.
  contain_scroll?.(chart);

  let library = names[0] ?? '';
  picker.value = library;
  let selected = null; // the selected term's name
  let revision = 0;
  const terms_now = () => results.get(library) || [];
  // Enrichr reports genes in upper case; match the tested genes case-insensitively.
  const in_term = () => {
    const term = terms_now().find((t) => t.name === selected);
    return new Set((term?.genes || []).map((g) => String(g).toUpperCase()));
  };

  const sync_link = () => {
    link.style.display = url ? '' : 'none';
    if (url) link.href = url;
    else link.removeAttribute('href');
  };

  // As in Enrich: with a term selected its genes are blue and the rest dark gray.
  const paint_genes = () => {
    const marked = in_term();
    paragraph.querySelectorAll('.clerk-gene').forEach((span) => {
      const hit = marked.has(span.dataset.gene.toUpperCase());
      span.classList.toggle('in-term', selected !== null && hit);
      span.classList.toggle('out-term', selected !== null && !hit);
    });
  };

  const draw = () => {
    const select = (term) => {
      selected = selected === term.name ? null : term.name;
      draw();
      paint_genes();
      // Like an Enrich term click: the term's genes show in the linked views.
      on_genes(selected ? term.genes.map(String) : []);
    };
    chart.replaceChildren();
    const terms = terms_now();
    if (!terms.length) {
      chart.textContent = 'No terms in this library.';
      return;
    }
    const max = Math.max(0, ...terms.map((t) => t.score)) || 1;
    terms.forEach((term) => {
      const bar = document.createElement('div');
      bar.className = 'clerk-enrichment-bar';
      bar.classList.toggle('selected', selected === term.name);
      bar.classList.toggle(
        'dimmed',
        selected !== null && selected !== term.name
      );
      bar.setAttribute('role', 'button');
      bar.tabIndex = 0;
      bar.setAttribute(
        'aria-label',
        `${term.name}: highlight its genes and show them in the views`
      );
      const fill = document.createElement('div');
      fill.className = 'clerk-enrichment-fill';
      fill.style.width = `${Math.max(0, (100 * term.score) / max)}%`;
      const name = document.createElement('span');
      name.className = 'clerk-enrichment-term';
      name.textContent = term.name;
      bar.append(fill, name);
      bar.addEventListener('mouseenter', (event) =>
        tooltip.show_html(term_html(term, esc), event)
      );
      bar.addEventListener('mousemove', (event) => tooltip.move(event));
      bar.addEventListener('mouseleave', () => tooltip.hide());
      bar.addEventListener('click', () => {
        tooltip.hide();
        select(term);
      });
      bar.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          select(term);
        }
      });
      chart.appendChild(bar);
    });
  };

  const show_library = async (name) => {
    const had_term = selected !== null;
    library = name;
    selected = null;
    if (had_term) on_genes([]);
    const mine = (revision += 1);
    if (!results.has(name) && fetch_terms) {
      chart.replaceChildren();
      chart.textContent = 'Loading…';
      paint_genes();
      try {
        const found = await fetch_terms(genes, name);
        if (mine !== revision) return;
        results.set(name, found?.terms || []);
        if (!url && ENRICHR_PAGE.test(found?.url || '')) ({ url } = found);
        sync_link();
      } catch (error) {
        if (mine !== revision) return;
        chart.textContent = `Couldn't reach Enrichr: ${error?.message || error}`;
        return;
      }
    }
    draw();
    paint_genes();
  };
  picker.addEventListener('change', () => show_library(picker.value));

  // The gene paragraph: every gene tested, in order.
  genes.forEach((gene, index) => {
    const span = document.createElement('span');
    span.className = 'clerk-gene';
    span.dataset.gene = gene;
    span.textContent = gene;
    span.tabIndex = 0;
    span.setAttribute('role', 'button');
    span.setAttribute(
      'aria-label',
      `${gene}: show on the Landscape and Clustergram (shift-click adds it)`
    );
    // Which of this library's top terms the gene is in, under its UniProt summary.
    const terms_html = () => {
      const upper = gene.toUpperCase();
      const hits = terms_now()
        .filter((t) => t.genes.some((g) => String(g).toUpperCase() === upper))
        .map((t) => esc(t.name));
      return hits.length ? `In: ${hits.join('; ')}` : '';
    };
    span.addEventListener('mouseenter', (event) =>
      tooltip.show(gene, event, terms_html())
    );
    span.addEventListener('mousemove', (event) => tooltip.move(event));
    span.addEventListener('mouseleave', () => tooltip.hide());
    span.addEventListener('click', (event) => {
      tooltip.hide();
      on_gene(gene, event.shiftKey);
    });
    span.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        on_gene(gene, event.shiftKey);
      }
    });
    paragraph.appendChild(span);
    if (index < genes.length - 1)
      paragraph.appendChild(document.createTextNode(', '));
  });

  sync_link();
  draw();
  return card;
};
