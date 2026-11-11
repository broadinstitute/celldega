/**
 * Enrichr results drawn inside Clerk, like the Enrich panel: a bar graph of the top
 * terms (one tab per library) and a paragraph of the genes tested.
 *
 * Hovering a bar shows the term's statistics; clicking it highlights the term's
 * genes in the paragraph and shows them in the linked views. Genes in the paragraph
 * behave like Clerk's other gene links: hover for UniProt, click to show.
 */

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
 * @param {{label: string, genes: string[], libraries: Object<string,
 *   Array<{name: string, score: number, adjusted_p?: number, odds_ratio?: number,
 *   genes: string[]}>>}} message - An `enrichment` message from Python.
 * @param {{on_gene: (gene: string, add: boolean) => void,
 *   on_genes: (genes: string[]) => void, tooltip: {show: Function,
 *   show_html: Function, move: Function, hide: Function},
 *   esc: (value: unknown) => string}} handlers
 * @returns {HTMLElement}
 */
export const render_enrichment = (
  message,
  { on_gene, on_genes, tooltip, esc }
) => {
  const libraries = Object.entries(message.libraries || {}).filter(
    ([, terms]) => terms?.length
  );
  const card = document.createElement('div');
  card.className = 'clerk-enrichment';

  const title = document.createElement('div');
  title.className = 'clerk-enrichment-title';
  title.textContent = `Enrichr · ${message.label || 'genes'}`;
  card.appendChild(title);

  const tabs = document.createElement('div');
  tabs.className = 'clerk-enrichment-tabs';
  const chart = document.createElement('div');
  chart.className = 'clerk-enrichment-bars';
  const paragraph = document.createElement('div');
  paragraph.className = 'clerk-enrichment-genes';
  card.append(tabs, chart, paragraph);

  let library = libraries[0]?.[0] ?? '';
  let selected = null; // the selected term's name
  const terms_now = () =>
    libraries.find(([name]) => name === library)?.[1] || [];
  // Enrichr reports genes in upper case; match the tested genes case-insensitively.
  const in_term = () => {
    const term = terms_now().find((t) => t.name === selected);
    return new Set((term?.genes || []).map((g) => String(g).toUpperCase()));
  };

  const paint_genes = () => {
    const marked = in_term();
    paragraph.querySelectorAll('.clerk-gene').forEach((span) => {
      span.classList.toggle(
        'in-term',
        marked.has(span.dataset.gene.toUpperCase())
      );
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
    tabs.replaceChildren();
    if (libraries.length > 1) {
      libraries.forEach(([name]) => {
        const tab = document.createElement('button');
        tab.className = 'clerk-tool';
        tab.textContent = name.replace(/_/g, ' ');
        tab.classList.toggle('active', name === library);
        tab.addEventListener('click', () => {
          library = name;
          selected = null;
          draw();
          paint_genes();
        });
        tabs.appendChild(tab);
      });
    }
    chart.replaceChildren();
    const terms = terms_now();
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

  // The gene paragraph: every gene tested, in order.
  (message.genes || []).forEach((gene, index) => {
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
      const names = terms_now()
        .filter((t) => t.genes.some((g) => String(g).toUpperCase() === upper))
        .map((t) => esc(t.name));
      return names.length ? `In: ${names.join('; ')}` : '';
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
    if (index < message.genes.length - 1)
      paragraph.appendChild(document.createTextNode(', '));
  });

  draw();
  return card;
};
