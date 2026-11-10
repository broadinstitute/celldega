/* global require */

// The Clerk chat panel: model picker <-> `model` trait, image preview, and listener
// cleanup. Loaded from source like the other widget tests (no Babel transform).
describe('Clerk panel', () => {
  let render_clerk;
  let turns;
  let tooltip;
  let contain_scroll;

  const make_model = (initial) => {
    const state = { ...initial };
    const listeners = new Map();
    return {
      get: (key) => state[key],
      set: (key, value) => {
        state[key] = value;
        (listeners.get(`change:${key}`) || []).forEach((handler) => handler());
      },
      save_changes: jest.fn(),
      on: (event, handler) => {
        listeners.set(event, [...(listeners.get(event) || []), handler]);
      },
      off: (event, handler) => {
        listeners.set(
          event,
          (listeners.get(event) || []).filter((h) => h !== handler)
        );
      },
      listener_count: () =>
        [...listeners.values()].reduce((n, handlers) => n + handlers.length, 0),
    };
  };

  beforeEach(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(path.join(__dirname, '../widgets/clerk_widget.js'), 'utf8')
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');
    // The real Markdown renderer, loaded the same way.
    const markdown_source = fs
      .readFileSync(path.join(__dirname, '../ui/markdown.js'), 'utf8')
      .replace(/^export const /gm, 'const ');
    const render_markdown = new Function(
      `${markdown_source}\nreturn render_markdown;`
    )();
    const turns_source = fs
      .readFileSync(path.join(__dirname, '../widgets/clerk_turns.js'), 'utf8')
      .replace(/^export const /gm, 'const ');
    turns = new Function(
      `${turns_source}\nreturn { group_turns, split_evidence, asks_question, link_genes, link_clusters };`
    )();
    contain_scroll = jest.fn();
    // A stand-in for the shared UniProt tooltip: records what it was asked to show.
    tooltip = {
      shown: [],
      show: jest.fn((gene) => tooltip.shown.push(gene)),
      show_html: jest.fn((html) => tooltip.shown.push(html)),
      move: jest.fn(),
      hide: jest.fn(),
      destroy: jest.fn(),
    };
    const factory = new Function(
      'postGeneList',
      'fetchEnrichment',
      'handleAsyncError',
      'contain_scroll',
      'make_gene_hover_tooltip',
      'render_markdown',
      'asks_question',
      'group_turns',
      'link_clusters',
      'link_genes',
      'split_evidence',
      `${source}\nreturn render_clerk;`
    );
    render_clerk = factory(
      jest.fn(),
      jest.fn(),
      jest.fn(),
      contain_scroll,
      () => tooltip,
      render_markdown,
      turns.asks_question,
      turns.group_turns,
      turns.link_clusters,
      turns.link_genes,
      turns.split_evidence
    );
  });

  const render = async (initial = {}) => {
    const model = make_model({
      width: 0,
      height: 400,
      gene_list: [],
      messages: [],
      pending: false,
      model: '',
      ...initial,
    });
    const el = document.createElement('div');
    const view = await render_clerk({ model, el });
    return { model, el, view, select: el.querySelector('select') };
  };

  test('the model picker reflects and sets the model trait', async () => {
    const { model, select } = await render({ model: 'sonnet' });
    expect(select.value).toBe('sonnet');
    expect([...select.options].map((o) => o.value)).toEqual([
      '',
      'opus',
      'sonnet',
      'haiku',
    ]);

    select.value = 'haiku';
    select.dispatchEvent(new Event('change'));
    expect(model.get('model')).toBe('haiku');
    expect(model.save_changes).toHaveBeenCalled();

    // Changes made from Python show up in the picker.
    model.set('model', 'opus');
    expect(select.value).toBe('opus');
  });

  test('the effort picker sets the effort trait', async () => {
    const { model, el } = await render({ model: '', effort: 'high' });
    const effort = el.querySelectorAll('select')[1];
    expect(effort.value).toBe('high');
    expect([...effort.options].map((o) => o.value)).toEqual([
      '',
      'low',
      'medium',
      'high',
      'xhigh',
      'max',
    ]);
    effort.value = 'max';
    effort.dispatchEvent(new Event('change'));
    expect(model.get('effort')).toBe('max');
  });

  test('a custom model id set from Python stays selectable', async () => {
    const { select } = await render({ model: 'claude-sonnet-5-5' });
    expect(select.value).toBe('claude-sonnet-5-5');
    expect(select.options).toHaveLength(5);
  });

  test('answers render as Markdown; questions and errors stay plain text', async () => {
    const { el } = await render({
      messages: [
        { role: 'user', content: '**not bold** <b>raw</b>' },
        { role: 'assistant', content: '## Findings\n- **MUC2** high' },
        { role: 'error', content: '<i>oops</i>' },
      ],
    });
    const answer = el.querySelector('.clerk-md');
    expect(answer.querySelector('h2').textContent).toBe('Findings');
    expect(answer.querySelector('li strong').textContent).toBe('MUC2');
    // User text and errors are shown literally, never as HTML.
    expect(el.querySelector('b')).toBeNull();
    expect(el.querySelector('i')).toBeNull();
    expect(el.textContent).toContain('**not bold** <b>raw</b>');
  });

  test('a question shows the screenshot and evidence it was sent with', async () => {
    const { el } = await render({
      messages: [
        {
          role: 'user',
          content: "What's in view?",
          image: 'VEhN',
          evidence: ['Landscape view', 'Clustergram: 25 rows x 15 columns'],
        },
        { role: 'assistant', content: 'Goblet cells.' },
      ],
    });
    const img = el.querySelector('img');
    expect(img.src).toContain('VEhN');
    expect(el.textContent).toContain(
      'Sent with: Landscape view · Clustergram: 25 rows x 15 columns'
    );
    // Only the one screenshot; the evidence strip has none.
    expect(el.querySelectorAll('img')).toHaveLength(1);
  });

  test('view changes Clerk made appear as their own line', async () => {
    const { el } = await render({
      messages: [
        { role: 'user', content: 'More markers?' },
        { role: 'assistant', content: 'Showing more.' },
        {
          role: 'action',
          content: 'Changed the Clustergram: DIM -> 10 markers per cluster',
        },
      ],
    });
    expect(el.textContent).toContain(
      '↻ Changed the Clustergram: DIM -> 10 markers per cluster'
    );
  });

  test('a full-width panel is capped for readability', async () => {
    const { el } = await render({ width: 0 });
    expect(el.firstChild.style.maxWidth).toBe('900px');
    const fixed = await render({ width: 600 });
    expect(fixed.el.firstChild.style.maxWidth).toBe('');
  });

  test('finalize removes every model listener', async () => {
    const { model, view } = await render();
    expect(model.listener_count()).toBeGreaterThan(0);
    view.finalize();
    expect(model.listener_count()).toBe(0);
  });
  test('a turn folds its work away and shows the final answer', async () => {
    const { el } = await render({
      messages: [
        { role: 'user', content: 'What is cluster 4?' },
        { role: 'action', content: 'Read the top 25 ranked markers' },
        { role: 'assistant', content: 'Checking more markers.' },
        { role: 'action', content: 'Ran Enrichr' },
        {
          role: 'assistant',
          content: 'Goblet cells.\n\nEvidence:\n- MUC2 high\n- TFF3 high',
        },
        {
          role: 'action',
          content: 'Recorded tentative cell types: 4 → Goblet',
        },
      ],
    });
    const turn = el.querySelector('details.clerk-turn');
    expect(turn.open).toBe(true);
    expect(turn.querySelector('summary').textContent).toContain(
      'What is cluster 4?'
    );
    const [work, evidence] = turn.querySelectorAll('details.clerk-fold');
    expect(work.querySelector('summary').textContent).toBe('Work · 3 steps');
    expect(work.open).toBe(false);
    expect(work.textContent).toContain('Checking more markers.');
    expect(evidence.querySelector('summary').textContent).toBe('Evidence');
    expect(evidence.open).toBe(false);
    expect(evidence.querySelectorAll('li')).toHaveLength(2);
    // The recorded cell types stay visible after the answer.
    expect(work.textContent).not.toContain('Recorded tentative');
    expect(turn.textContent).toContain('↻ Recorded tentative cell types');
  });

  test('work stays open while Clerk is working, and folds keep their state', async () => {
    const { el, model } = await render({
      pending: true,
      messages: [
        { role: 'user', content: 'q' },
        { role: 'action', content: 'Looked up MUC2' },
      ],
    });
    const work = () => el.querySelector('details.clerk-fold');
    expect(work().open).toBe(true);
    expect(el.textContent).toContain('Clerk is working…');
    // The scientist closes it; a new message re-renders but keeps it closed.
    work().querySelector('summary').click();
    model.set('messages', [
      ...model.get('messages'),
      { role: 'action', content: 'Ran Enrichr' },
    ]);
    expect(work().open).toBe(false);
  });

  test('a closing question offers a Yes button that answers it', async () => {
    const { el, model } = await render({
      messages: [
        { role: 'user', content: 'q' },
        {
          role: 'assistant',
          content: 'Goblet cells.\n\nEvidence:\n- MUC2\n\nCheck cluster 7?',
        },
      ],
    });
    // The question stays visible after the collapsed evidence.
    expect(el.querySelector('details.clerk-fold').textContent).not.toContain(
      'Check cluster 7?'
    );
    const yes = [...el.querySelectorAll('button')].find(
      (b) => b.textContent === 'Yes'
    );
    yes.click();
    expect(model.get('request')).toMatchObject({ question: 'Yes' });
    expect(model.save_changes).toHaveBeenCalled();
  });

  test('no Yes button for a statement or an earlier question', async () => {
    const { el } = await render({
      messages: [
        { role: 'user', content: 'q1' },
        { role: 'assistant', content: 'Check 7?' },
        { role: 'user', content: 'q2' },
        { role: 'assistant', content: 'Done.' },
      ],
    });
    const labels = [...el.querySelectorAll('button')].map((b) => b.textContent);
    expect(labels).not.toContain('Yes');
  });

  test('a pause offers Continue, which resumes the question', async () => {
    const { el, model } = await render({
      messages: [
        { role: 'user', content: 'q' },
        { role: 'action', content: 'Looked up MUC2' },
        { role: 'pause', content: 'Clerk paused. Continue?' },
      ],
    });
    const button = [...el.querySelectorAll('button')].find(
      (b) => b.textContent === 'Continue'
    );
    button.click();
    expect(model.get('request')).toMatchObject({ continue: true });
  });

  test('Expand all opens every fold; Export asks Python for a report', async () => {
    const { el, model } = await render({
      messages: [
        { role: 'user', content: 'q' },
        { role: 'action', content: 'Looked up MUC2' },
        { role: 'assistant', content: 'A.\n\nEvidence:\n- MUC2' },
      ],
    });
    const button = (text) =>
      [...el.querySelectorAll('button')].find((b) => b.textContent === text);
    button('Expand all').click();
    expect([...el.querySelectorAll('details')].every((d) => d.open)).toBe(true);
    button('Collapse all').click();
    expect([...el.querySelectorAll('details')].every((d) => !d.open)).toBe(
      true
    );
    // Re-rendering keeps them collapsed.
    model.set('messages', [...model.get('messages')]);
    expect(el.querySelector('details.clerk-turn').open).toBe(false);
    button('Export').click();
    expect(model.get('request')).toMatchObject({ export: true });
  });

  test('group_turns, split_evidence and asks_question', () => {
    const grouped = turns.group_turns(
      [
        { role: 'error', content: 'early' },
        { role: 'user', content: 'q' },
        { role: 'assistant', content: 'interim' },
        { role: 'assistant', content: 'final' },
      ],
      false
    );
    expect(grouped).toHaveLength(2);
    expect(grouped[0].question).toBeNull();
    expect(grouped[0].errors).toHaveLength(1);
    expect(grouped[1].answer.content).toBe('final');
    expect(grouped[1].work.map((m) => m.content)).toEqual(['interim']);
    // While pending, nothing is final yet.
    expect(turns.group_turns(grouped[1].work, true)[0].answer).toBeNull();

    expect(
      turns.split_evidence('A.\n**Evidence:**\n- x\n  more\n- y\n\nOK?')
    ).toEqual({
      main: 'A.',
      evidence: '- x\n  more\n- y',
      after: 'OK?',
    });
    expect(turns.split_evidence('Evidence suggests x.').evidence).toBeNull();
    expect(turns.asks_question('Shall I check cluster 7?**')).toBe(true);
    expect(turns.asks_question('Done.')).toBe(false);
  });
  test('a loaded briefing is shown above the conversation', async () => {
    const { el, model } = await render({ briefing_label: '' });
    expect(el.textContent).not.toContain('Briefing:');
    model.set(
      'briefing_label',
      'Briefing: 1,200 characters of earlier work from case1'
    );
    expect(el.textContent).toContain(
      'Briefing: 1,200 characters of earlier work from case1'
    );
  });
  const answer_with = (content, extra = {}) => [
    { role: 'user', content: 'q' },
    { role: 'assistant', content, ...extra },
  ];

  test('genes in answers link to the Landscape and Clustergram', async () => {
    const { el, model } = await render({
      messages: answer_with('MUC2 and tff3 are high; the cat is not.', {
        genes: ['MUC2', 'TFF3', 'CAT'],
      }),
    });
    const links = [...el.querySelectorAll('.clerk-gene')];
    // A lower-case word without digits ("cat") isn't linked: it's probably English.
    expect(links.map((l) => l.textContent)).toEqual(['MUC2', 'tff3']);
    expect(links[1].dataset.gene).toBe('TFF3');

    links[0].dispatchEvent(new MouseEvent('mouseenter'));
    expect(tooltip.show).toHaveBeenCalledWith('MUC2', expect.anything());

    links[0].click();
    expect(model.get('request')).toMatchObject({
      show_genes: ['MUC2'],
      focus: 'MUC2',
    });
    expect(links[0].classList.contains('shown')).toBe(true);
    links[1].dispatchEvent(new MouseEvent('click', { shiftKey: true }));
    expect(model.get('request').show_genes).toEqual(['MUC2', 'TFF3']);
    links[1].dispatchEvent(new MouseEvent('click', { shiftKey: true }));
    links[0].click(); // the only gene shown, clicked again: back to clusters
    expect(model.get('request').show_genes).toEqual([]);
  });

  test('cluster references link to the Landscape, with labels on hover', async () => {
    const { el, model } = await render({
      cluster_names: ['4', '5', '12'],
      cluster_labels: { 4: 'Goblet-like (Clerk, tentative)' },
      messages: answer_with(
        'Clusters 4, 5 and 9 differ; cluster 12 too. Use 25 markers.'
      ),
    });
    const links = [...el.querySelectorAll('.clerk-cluster')];
    expect(links.map((l) => l.textContent)).toEqual(['4', '5', '12']);
    links[0].dispatchEvent(new MouseEvent('mouseenter'));
    expect(tooltip.show_html.mock.calls.at(-1)[0]).toContain(
      'Goblet-like (Clerk, tentative)'
    );
    links[2].click();
    expect(model.get('request')).toMatchObject({ show_clusters: ['12'] });
  });

  test('cited views are links that apply the view', async () => {
    const views = {
      '1A': {
        caption: 'Cluster A at low zoom',
        landscape: { clusters: ['A'], reset_view: true },
      },
    };
    const { el, model } = await render({
      messages: answer_with(
        'A forms a ring [Fig 1A](view:1A) but not [Fig 9](view:9).',
        { views }
      ),
    });
    const link = el.querySelector('a.clerk-view');
    expect(link.textContent).toBe('Fig 1A');
    // An undefined view is left as plain text.
    expect(el.querySelectorAll('a.clerk-view')).toHaveLength(1);
    expect(el.textContent).toContain('but not Fig 9.');
    link.dispatchEvent(new MouseEvent('mouseenter'));
    expect(tooltip.show_html.mock.calls.at(-1)[0]).toContain(
      'Cluster A at low zoom'
    );
    link.click();
    expect(model.get('request')).toMatchObject({
      apply_view: { landscape: { clusters: ['A'], reset_view: true } },
    });
    expect(link.classList.contains('shown')).toBe(true);
  });

  test('a gene count in the work log lists and shows the genes', async () => {
    const genes = Array.from({ length: 25 }, (_, i) => `G${i}`);
    const { el, model } = await render({
      messages: [
        { role: 'user', content: 'q' },
        {
          role: 'action',
          content: 'Looked up 25 genes in the Clustergram (view unchanged)',
          genes,
        },
        { role: 'assistant', content: 'Done.' },
      ],
    });
    const span = el.querySelector('.clerk-genelist');
    expect(span.textContent).toBe('25 genes');
    span.dispatchEvent(new MouseEvent('mouseenter'));
    expect(tooltip.show_html.mock.calls.at(-1)[0]).toContain('G0, G1');
    span.click();
    // At most 20 genes at once, as in the Landscape's gene search.
    expect(model.get('request').show_genes).toHaveLength(20);
  });

  test('evidence links work while Clerk is answering', async () => {
    const { el, model } = await render({
      pending: true,
      messages: [
        { role: 'user', content: 'q' },
        { role: 'assistant', content: 'Checking MUC2.', genes: ['MUC2'] },
      ],
    });
    el.querySelector('.clerk-gene').click();
    expect(model.get('request')).toMatchObject({ show_genes: ['MUC2'] });
  });

  test('Back appears once links changed the views and restores them', async () => {
    const { el, model } = await render({ can_restore: false });
    const back = [...el.querySelectorAll('button')].find(
      (b) => b.textContent === 'Back to your view'
    );
    expect(back.style.display).toBe('none');
    model.set('can_restore', true);
    expect(back.style.display).toBe('');
    back.click();
    expect(model.get('request')).toMatchObject({ restore_view: true });
  });

  test('Yes and No answer a closing question', async () => {
    const { el, model } = await render({
      messages: answer_with('Check cluster 7?'),
    });
    const buttons = [...el.querySelectorAll('button.clerk-button')];
    expect(buttons.map((b) => b.textContent)).toEqual(['Yes', 'No']);
    buttons[1].click();
    expect(model.get('request')).toMatchObject({ question: 'No' });
  });

  test('finalize removes the gene tooltip', async () => {
    const { view } = await render();
    view.finalize();
    expect(tooltip.destroy).toHaveBeenCalled();
  });
  test('scrolling the conversation never scrolls the notebook page', async () => {
    const { el } = await render();
    const contained = contain_scroll.mock.calls.map(([element]) => element);
    // The conversation pane (the scrolling one with the turns) and the gene strip.
    expect(contained).toHaveLength(2);
    expect(contained.every((element) => el.contains(element))).toBe(true);
    expect(contained[0].style.overflowY).toBe('auto');
  });
});
