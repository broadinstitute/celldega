/* global require */

// Enrichr results drawn inside Clerk, like the Enrich panel.
const load = (file, names) => {
  const fs = require('fs');
  const path = require('path');
  const source = fs
    .readFileSync(path.join(__dirname, file), 'utf8')
    .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
    .replace(/^export const /gm, 'const ');
  return new Function(`${source}\nreturn { ${names} };`)();
};

const { render_enrichment, term_html } = load(
  '../widgets/clerk_enrichment.js',
  'render_enrichment, term_html'
);

const esc = (value) => String(value).replace(/</g, '&lt;');

const MESSAGE = {
  role: 'enrichment',
  label: "cluster 4's top 3 markers",
  genes: ['Muc2', 'TFF3', 'JCHAIN'],
  libraries: {
    CellMarker_2024: [
      {
        name: 'Goblet cell',
        score: 40,
        adjusted_p: 0.001,
        odds_ratio: 12,
        genes: ['MUC2', 'TFF3'],
      },
      { name: 'Plasma cell', score: 10, genes: ['JCHAIN'] },
    ],
    PanglaoDB_Augmented_2021: [
      { name: 'Enterocytes', score: 5, genes: ['TFF3'] },
    ],
  },
};

const setup = (message = MESSAGE) => {
  const handlers = {
    on_gene: jest.fn(),
    on_genes: jest.fn(),
    tooltip: {
      show: jest.fn(),
      show_html: jest.fn(),
      move: jest.fn(),
      hide: jest.fn(),
    },
    esc,
  };
  const card = render_enrichment(message, handlers);
  document.body.replaceChildren(card);
  const bars = () => [...card.querySelectorAll('.clerk-enrichment-bar')];
  const genes = () => [...card.querySelectorAll('.clerk-gene')];
  return { card, handlers, bars, genes };
};

describe('inline Enrichr results', () => {
  test('a bar per top term of the first library, sized by combined score', () => {
    const { card, bars, genes } = setup();
    expect(card.querySelector('.clerk-enrichment-title').textContent).toBe(
      "Enrichr · cluster 4's top 3 markers"
    );
    expect(bars().map((bar) => bar.textContent)).toEqual([
      'Goblet cell',
      'Plasma cell',
    ]);
    const widths = bars().map(
      (bar) => bar.querySelector('.clerk-enrichment-fill').style.width
    );
    expect(widths).toEqual(['100%', '25%']);
    expect(genes().map((gene) => gene.textContent)).toEqual([
      'Muc2',
      'TFF3',
      'JCHAIN',
    ]);
  });

  test('clicking a term highlights its genes and shows them; clicking again clears', () => {
    const { bars, genes, handlers } = setup();
    bars()[0].click();
    expect(bars()[0].classList.contains('selected')).toBe(true);
    expect(bars()[1].classList.contains('dimmed')).toBe(true);
    // Enrichr's upper-case genes match the tested genes whatever their case.
    expect(
      genes()
        .filter((g) => g.classList.contains('in-term'))
        .map((g) => g.textContent)
    ).toEqual(['Muc2', 'TFF3']);
    expect(handlers.on_genes).toHaveBeenLastCalledWith(['MUC2', 'TFF3']);
    bars()[0].click();
    expect(genes().some((g) => g.classList.contains('in-term'))).toBe(false);
    expect(handlers.on_genes).toHaveBeenLastCalledWith([]);
  });

  test('one tab per library; switching clears the selection', () => {
    const { card, bars } = setup();
    const tabs = [...card.querySelectorAll('.clerk-enrichment-tabs button')];
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      'CellMarker 2024',
      'PanglaoDB Augmented 2021',
    ]);
    bars()[0].click();
    tabs[1].click();
    expect(bars().map((bar) => bar.textContent)).toEqual(['Enterocytes']);
    expect(bars()[0].classList.contains('selected')).toBe(false);
    const single = setup({
      ...MESSAGE,
      libraries: { CellMarker_2024: MESSAGE.libraries.CellMarker_2024 },
    });
    expect(
      single.card.querySelectorAll('.clerk-enrichment-tabs button')
    ).toHaveLength(0);
  });

  test('hovering shows term statistics and genes their UniProt summary and terms', () => {
    const { bars, genes, handlers } = setup();
    bars()[0].dispatchEvent(new MouseEvent('mouseenter'));
    const html = handlers.tooltip.show_html.mock.calls[0][0];
    expect(html).toContain('<b>Goblet cell</b>');
    expect(html).toContain('Adjusted p 0.0010');
    expect(html).toContain('Genes: MUC2, TFF3');
    genes()[1].dispatchEvent(new MouseEvent('mouseenter'));
    expect(handlers.tooltip.show).toHaveBeenLastCalledWith(
      'TFF3',
      expect.anything(),
      'In: Goblet cell'
    );
  });

  test('a gene click shows it in the views like any Clerk gene link', () => {
    const { genes, handlers } = setup();
    genes()[2].dispatchEvent(new MouseEvent('click', { shiftKey: true }));
    expect(handlers.on_gene).toHaveBeenCalledWith('JCHAIN', true);
  });

  test('term_html leaves out statistics a term lacks', () => {
    expect(term_html({ name: 'X', score: 2, genes: [] }, esc)).toBe(
      '<b>X</b><br>Combined score 2.00'
    );
  });
});

describe('turns', () => {
  const { group_turns } = load('../widgets/clerk_turns.js', 'group_turns');

  test('Enrichr results are figures in view, not steps in Work', () => {
    const [turn] = group_turns([
      { role: 'user', content: 'What is cluster 4?' },
      { role: 'action', content: 'Ran Enrichr' },
      MESSAGE,
      { role: 'assistant', content: 'Goblet-like.' },
    ]);
    expect(turn.figures).toEqual([MESSAGE]);
    expect(turn.work.map((m) => m.role)).toEqual(['action']);
    expect(turn.answer.content).toBe('Goblet-like.');
  });
});
