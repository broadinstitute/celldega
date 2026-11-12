/* global require */

// The Clerk chat panel: model picker <-> `model` trait, image preview, and listener
// cleanup. Loaded from source like the other widget tests (no Babel transform).
describe('Clerk panel', () => {
  let render_clerk;
  let turns;
  let tooltip;
  let contain_scroll;
  let enrichr;

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
      'render_enrichment',
      `${source}\nreturn render_clerk;`
    );
    enrichr = {
      post: jest.fn(async () => ({ userListId: '7', shortId: 'Sh0rt' })),
      fetch: jest.fn(async (_id, library) => ({
        [library]: [
          [1, 'Goblet', 0.001, 9, 30, ['MUC2'], 0.01],
          [2, 'Paneth', 0.01, 3, 5, ['TFF3'], 0.05],
        ],
      })),
    };
    render_clerk = factory(
      enrichr.post,
      enrichr.fetch,
      jest.fn(),
      contain_scroll,
      () => tooltip,
      render_markdown,
      turns.asks_question,
      turns.group_turns,
      turns.link_clusters,
      turns.link_genes,
      turns.split_evidence,
      new Function(
        `${fs
          .readFileSync(
            path.join(__dirname, '../widgets/clerk_enrichment.js'),
            'utf8'
          )
          .replace(/^export const /gm, 'const ')}\nreturn render_enrichment;`
      )()
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

  test('a question shows both views it was sent with, and links back to them', async () => {
    const snapshots = {
      landscape: { state: { view: { zoom: 2, target: [10, 20, 0] } } },
      clustergram: { state: { focus_gene: 'MUC2' } },
    };
    const { el, model } = await render({
      pending: true,
      messages: [
        {
          role: 'user',
          content: "What's in view?",
          image: 'VEhN',
          clustergram_image: 'Q0dN',
          snapshots,
          evidence: ['Landscape view', 'Clustergram: 25 rows x 15 columns'],
        },
        { role: 'assistant', content: 'Goblet cells.' },
      ],
    });
    const images = [...el.querySelectorAll('.clerk-sent-image img')];
    expect(images.map((img) => img.src.slice(-4))).toEqual(['VEhN', 'Q0dN']);
    expect(images.map((img) => img.title)).toEqual([
      'Landscape view sent with this question',
      'Clustergram view sent with this question',
    ]);
    expect(el.textContent).toContain(
      'Sent with: Landscape view · Clustergram: 25 rows x 15 columns'
    );
    // Each link works while Clerk is answering and restores that capture, not the
    // widgets' current state; the last one restores both.
    const links = [...el.querySelectorAll('a.clerk-image-view')];
    expect(links.map((link) => link.textContent)).toEqual([
      'Show this view',
      'Show this view',
      'Show both views',
    ]);
    links[1].click();
    expect(model.get('request').show_snapshot).toEqual({
      clustergram: snapshots.clustergram,
    });
    links[0].click();
    expect(model.get('request').show_snapshot).toEqual({
      landscape: snapshots.landscape,
    });
    links[2].click();
    expect(model.get('request').show_snapshot).toEqual(snapshots);

    // A question about the Clustergram alone shows its image only.
    model.set('messages', [
      {
        role: 'user',
        content: 'q',
        clustergram_image: 'Q0dN',
        snapshots: { clustergram: snapshots.clustergram },
      },
    ]);
    expect(el.querySelectorAll('.clerk-sent-image img')).toHaveLength(1);
    expect(
      [...el.querySelectorAll('a.clerk-image-view')].map((l) => l.textContent)
    ).toEqual(['Show this view']);
    // Older screenshots without replay state are still shown without a dead link.
    model.set('messages', [{ role: 'user', content: 'old', image: 'VEhN' }]);
    expect(el.querySelector('img')).not.toBeNull();
    expect(el.querySelector('a.clerk-image-view')).toBeNull();
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

  test('Expand opens every fold; Report asks Python for a report', async () => {
    const { el, model } = await render({
      messages: [
        { role: 'user', content: 'q' },
        { role: 'action', content: 'Looked up MUC2' },
        { role: 'assistant', content: 'A.\n\nEvidence:\n- MUC2' },
      ],
    });
    const button = (text) =>
      [...el.querySelectorAll('button')].find((b) => b.textContent === text);
    button('Expand').click();
    expect([...el.querySelectorAll('details')].every((d) => d.open)).toBe(true);
    button('Collapse').click();
    expect([...el.querySelectorAll('details')].every((d) => !d.open)).toBe(
      true
    );
    // Re-rendering keeps them collapsed.
    model.set('messages', [...model.get('messages')]);
    expect(el.querySelector('details.clerk-turn').open).toBe(false);
    button('Report').click();
    const reportForm = el.querySelector('.clerk-report-form');
    expect(reportForm.hidden).toBe(false);
    expect(model.get('request')).toBeUndefined();
    reportForm.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(model.get('request')).toMatchObject({
      export: true,
      report_title: '',
    });
    expect(reportForm.hidden).toBe(true);
    button('Save').click();
    expect(model.get('request')).toMatchObject({ save_conversation: true });
  });

  test('Report accepts a name and Cancel writes nothing', async () => {
    const { el, model } = await render();
    const open = [...el.querySelectorAll('.clerk-tool')].find(
      (button) => button.textContent === 'Report'
    );
    const form = el.querySelector('.clerk-report-form');
    const name = form.querySelector('input');
    expect(form.hidden).toBe(true);
    open.click();
    name.value = ' Kidney exploration ';
    [...form.querySelectorAll('button')]
      .find((b) => b.textContent === 'Cancel')
      .click();
    expect(form.hidden).toBe(true);
    expect(model.get('request')).toBeUndefined();
    open.click();
    form.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(model.get('request')).toMatchObject({
      export: true,
      report_title: 'Kidney exploration',
    });
    expect(form.hidden).toBe(true);
  });

  test('Open reads a saved conversation and sends it to Python once', async () => {
    const { el, model } = await render();
    model.send = jest.fn();
    const opener = el.querySelector('input[type="file"]');
    const clicked = jest.spyOn(opener, 'click').mockImplementation(() => {});
    [...el.querySelectorAll('button')]
      .find((b) => b.textContent === 'Open')
      .click();
    expect(clicked).toHaveBeenCalled();
    const file = new File(['{"celldega_clerk_conversation": 1}'], 'talk.json');
    file.text = async () => '{"celldega_clerk_conversation": 1}';
    Object.defineProperty(opener, 'files', { value: [file] });
    opener.dispatchEvent(new Event('change'));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(model.send).toHaveBeenCalledWith({
      event: 'load_conversation',
      name: 'talk.json',
      text: '{"celldega_clerk_conversation": 1}',
    });
  });

  test('Enrichr results render under the answer, linked to the views', async () => {
    const { el, model } = await render({
      messages: [
        { role: 'user', content: 'q' },
        {
          role: 'enrichment',
          label: '2 selected genes',
          genes: ['MUC2', 'TFF3'],
          libraries: {
            CellMarker_2024: [{ name: 'Goblet', score: 3, genes: ['MUC2'] }],
          },
        },
        { role: 'assistant', content: 'Goblet-like.' },
      ],
    });
    expect(
      el.querySelector('.clerk-enrichment .clerk-enrichment-term').textContent
    ).toBe('Goblet');
    el.querySelector('.clerk-enrichment-bar').click();
    expect(model.get('request')).toMatchObject({ show_genes: ['MUC2'] });
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
      (b) => b.textContent === 'Return'
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
    const buttons = [...el.querySelectorAll('.clerk-turn button.clerk-button')];
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
    // The conversation pane (the scrolling one with the turns).
    expect(contained).toHaveLength(1);
    expect(contained.every((element) => el.contains(element))).toBe(true);
    expect(contained[0].style.overflowY).toBe('auto');
  });
  test('a question sends the Enrichr page of the selected genes', async () => {
    const { el, model } = await render({ gene_list: ['MUC2'] });
    el.querySelector('textarea').value = 'What is this?';
    el.querySelector('button.clerk-ask').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(model.get('request')).toMatchObject({
      question: 'What is this?',
      enrichr_library: 'CellMarker_2024',
      enrichr_short_id: 'Sh0rt',
    });
    expect(model.get('request').enrichr_terms[0]).toMatchObject({
      name: 'Goblet',
      adjusted_p: 0.01,
      odds_ratio: 9,
    });
  });

  test('Enrichr results fold under their title', async () => {
    const { el } = await render({
      messages: [
        { role: 'user', content: 'q' },
        {
          role: 'enrichment',
          title: 'Cluster 4 upregulated',
          label: "cluster 4's top 2 markers",
          genes: ['MUC2', 'TFF3'],
          libraries: {
            CellMarker_2024: [{ name: 'Goblet', score: 3, genes: ['MUC2'] }],
          },
        },
        { role: 'assistant', content: 'Goblet-like.' },
      ],
    });
    const fold = el.querySelector('details.clerk-figure');
    expect(fold.open).toBe(false);
    expect(fold.querySelector('summary').textContent).toBe(
      'Enrichr · Cluster 4 upregulated'
    );
    expect(fold.querySelector('.clerk-enrichment-title')).toBeNull();
  });

  test('recorded cell types: one short line, details in Evidence, and a Label offer', async () => {
    const offer = {
      id: 'o1',
      status: 'offered',
      cell_types: [{ cluster: '4', label: 'Goblet', markers: ['MUC2'] }],
    };
    const messages = [
      { role: 'user', content: 'q' },
      {
        role: 'assistant',
        content: 'Goblet cells.\n\nEvidence:\n- MUC2 high',
        genes: ['MUC2'],
      },
      {
        role: 'action',
        content: 'Recorded tentative cell types for 1 cluster',
        detail: 'Recorded cell types: 4 → Goblet (high)',
        label_offer: offer,
      },
    ];
    const { el, model } = await render({ messages, cluster_names: ['4'] });
    model.send = jest.fn();
    expect(el.textContent).toContain(
      '↻ Recorded tentative cell types for 1 cluster'
    );
    const evidence = [...el.querySelectorAll('details.clerk-fold')].find(
      (d) => d.querySelector('summary').textContent === 'Evidence'
    );
    expect(evidence.querySelector('.clerk-recorded').textContent).toBe(
      'Recorded cell types: 4 → Goblet (high)'
    );
    expect(el.querySelector('.clerk-offer').textContent).toContain(
      'Label these clusters in the Clustergram?'
    );
    const label = [...el.querySelectorAll('button')].find(
      (b) => b.textContent === 'Label'
    );
    label.click();
    expect(model.send).toHaveBeenCalledWith({
      event: 'label_clustergram',
      id: 'o1',
    });

    // Once applied, the offer becomes a line saying what changed.
    messages[2] = {
      ...messages[2],
      label_offer: {
        ...offer,
        status: 'done',
        result: 'Labeled 1 Clustergram column',
      },
    };
    model.set('messages', [...messages]);
    expect(el.querySelector('.clerk-offer')).toBeNull();
    expect(el.textContent).toContain('↻ Labeled 1 Clustergram column');

    // No offer while Clerk is answering.
    messages[2] = { ...messages[2], label_offer: offer };
    model.set('pending', true);
    model.set('messages', [...messages]);
    expect(el.querySelector('.clerk-offer')).toBeNull();
  });

  test('genes and clusters inside a cited view link are links of their own', async () => {
    const views = {
      '1A': { landscape: { clusters: ['16'], genes: ['PODXL'] } },
    };
    const { el, model } = await render({
      cluster_names: ['16'],
      messages: answer_with(
        '[cluster 16 podocytes (PODXL)](view:1A) line the tuft.',
        {
          genes: ['PODXL'],
          views,
        }
      ),
    });
    const view = el.querySelector('a.clerk-view');
    view.querySelector('.clerk-cluster').click();
    expect(model.get('request')).toMatchObject({ show_clusters: ['16'] });
    expect(model.get('request').apply_view).toBeUndefined();
    view.querySelector('.clerk-gene').click();
    expect(model.get('request')).toMatchObject({ show_genes: ['PODXL'] });
    // The rest of the link still shows the view.
    view.click();
    expect(model.get('request')).toMatchObject({ apply_view: views['1A'] });
  });

  test('a view selecting a dendrogram group says so on hover', async () => {
    const views = {
      '2A': {
        clustergram: {
          dendrogram: { col: 40 },
          selection: { dendrogram: { axis: 'col', members: ['4', '5'] } },
        },
      },
    };
    const { el } = await render({
      messages: answer_with('[Fig 2A](view:2A)', { views }),
    });
    el.querySelector('a.clerk-view').dispatchEvent(
      new MouseEvent('mouseenter')
    );
    expect(tooltip.show_html.mock.calls.at(-1)[0]).toContain(
      'Clustergram column dendrogram group of 2'
    );
  });
  test('brackets around gene and cluster names are dropped', async () => {
    const { el } = await render({
      cluster_names: ['27'],
      messages: answer_with(
        'Cluster [27] carries ([MYH11], [ACTA2]), not [Fig 9] or [n=3].',
        { genes: ['MYH11', 'ACTA2'] }
      ),
    });
    const body = el.querySelector('.clerk-md');
    expect(body.textContent).toBe(
      'Cluster 27 carries (MYH11, ACTA2), not [Fig 9] or [n=3].'
    );
    expect(
      [...body.querySelectorAll('.clerk-gene')].map((g) => g.textContent)
    ).toEqual(['MYH11', 'ACTA2']);
    expect(body.querySelector('.clerk-cluster').textContent).toBe('27');
  });
  test('cluster lists are links in sentences about clusters', async () => {
    const { el, model } = await render({
      cluster_names: ['5', '7', '12', '13', '16', '20', '25', '26'],
      messages: answer_with(
        'Confidence high for 20, 5, 16, 26, 12; medium for 13/25; cluster 7 is ' +
          'uncertain (SLC4A11, ITGB3).\n\nThe top 12, 25 markers were checked.\n\n' +
          'Values 5, 7 and 12 are rounded.',
        { genes: ['SLC4A11', 'ITGB3'] }
      ),
    });
    const paragraphs = [...el.querySelectorAll('.clerk-md p')];
    const linked = (p) =>
      [...p.querySelectorAll('.clerk-cluster')].map((l) => l.textContent);
    expect(linked(paragraphs[0])).toEqual([
      '20',
      '5',
      '16',
      '26',
      '12',
      '13',
      '25',
      '7',
    ]);
    // A list followed by a unit is a quantity; a sentence not about clusters is left
    // alone.
    expect(linked(paragraphs[1])).toEqual([]);
    expect(linked(paragraphs[2])).toEqual([]);
    paragraphs[0].querySelectorAll('.clerk-cluster')[1].click();
    expect(model.get('request')).toMatchObject({ show_clusters: ['5'] });
  });
  test('a drafted analysis notebook can be run with Claude Code from its line', async () => {
    const analysis = {
      id: 'a1',
      title: 'Signature score',
      path: '/work/clerk_files/analyses/signature_score.ipynb',
      status: 'drafted',
      summary: '',
    };
    const messages = [
      { role: 'user', content: 'q' },
      { role: 'assistant', content: 'A signature score would settle it.' },
      {
        role: 'action',
        content: 'Drafted an analysis notebook: Signature score',
        detail: `Analysis notebook: ${analysis.path}`,
        analysis,
      },
    ];
    const { el, model } = await render({ messages });
    model.send = jest.fn();
    expect(el.querySelector('.clerk-analysis-path').textContent).toBe(
      analysis.path
    );
    expect(el.querySelector('.clerk-analysis').textContent).toContain(
      'Inspect it before running it.'
    );
    const run = [...el.querySelectorAll('button')].find(
      (b) => b.textContent === 'Run with Claude Code'
    );
    run.click();
    expect(model.send).toHaveBeenCalledWith({
      event: 'run_analysis',
      id: 'a1',
    });

    messages[2] = {
      ...messages[2],
      analysis: { ...analysis, status: 'running' },
    };
    model.set('messages', [...messages]);
    expect(el.querySelector('.clerk-analysis').textContent).toContain(
      'Claude Code is running it…'
    );
    expect(
      [...el.querySelectorAll('button')].some((b) =>
        b.textContent.includes('Claude Code')
      )
    ).toBe(false);

    messages[2] = {
      ...messages[2],
      analysis: { ...analysis, status: 'done', summary: 'Scored 3 clusters.' },
    };
    model.set('messages', [...messages]);
    const box = el.querySelector('.clerk-analysis');
    expect(box.textContent).toContain('Claude Code ran it');
    expect(box.querySelector('details .clerk-recorded').textContent).toBe(
      'Scored 3 clusters.'
    );
  });
  test('a notebook Clerk suggests is drafted only when the scientist says so', async () => {
    const messages = [
      { role: 'user', content: 'q' },
      { role: 'assistant', content: 'A signature score would settle it.' },
      {
        role: 'action',
        content: 'Suggested an analysis notebook: Signature score',
        detail: 'Score a signature across the clusters.',
        notebook_offer: {
          id: 'n1',
          status: 'offered',
          title: 'Signature score',
          purpose: 'Score a signature across the clusters.',
        },
      },
    ];
    const { el, model } = await render({ messages });
    model.send = jest.fn();
    const box = el.querySelector('.clerk-analysis');
    expect(box.textContent).toContain('Score a signature across the clusters.');
    expect(box.textContent).toContain(
      'Draft this notebook for you to inspect?'
    );
    // No path and no Run button before it's drafted.
    expect(el.querySelector('.clerk-analysis-path')).toBeNull();
    expect(
      [...el.querySelectorAll('button')].some((b) =>
        b.textContent.includes('Claude Code')
      )
    ).toBe(false);
    [...el.querySelectorAll('button')]
      .find((b) => b.textContent === 'Draft notebook')
      .click();
    expect(model.send).toHaveBeenCalledWith({
      event: 'draft_notebook',
      id: 'n1',
    });
  });
});
