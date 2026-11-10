import { postGeneList, fetchEnrichment } from '../external_apis/enrichr_api';
import { handleAsyncError } from '../temp_utils/errorHandler';
import { contain_scroll, make_gene_hover_tooltip } from '../ui/gene_info';
import { render_markdown } from '../ui/markdown';

import {
  asks_question,
  group_turns,
  link_clusters,
  link_genes,
  split_evidence,
} from './clerk_turns';

const FONT =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

// Library used to pre-gather Enrichr evidence that rides along in the prompt.
const ENRICHR_LIB = 'CellMarker_2024';
const ENRICHR_TERMS = 8;

// Most genes one click shows (the Landscape's gene search allows 20).
const MAX_SHOWN_GENES = 20;

// A full-width panel is capped here so chat text stays readable.
const MAX_PANEL_WIDTH = 900;

// Styles for rendered Markdown, scoped to the panel's class so they can't leak into
// the rest of the notebook.
const PANEL_CLASS = 'celldega-clerk';
const MARKDOWN_CSS = `
.${PANEL_CLASS} .clerk-md p { margin: 4px 0; }
.${PANEL_CLASS} .clerk-md h1, .${PANEL_CLASS} .clerk-md h2 { font-size: 15px; margin: 10px 0 4px; }
.${PANEL_CLASS} .clerk-md h3, .${PANEL_CLASS} .clerk-md h4,
.${PANEL_CLASS} .clerk-md h5, .${PANEL_CLASS} .clerk-md h6 { font-size: 14px; margin: 8px 0 3px; }
.${PANEL_CLASS} .clerk-md ul, .${PANEL_CLASS} .clerk-md ol { margin: 3px 0; padding-left: 22px; }
.${PANEL_CLASS} .clerk-md li { margin: 1px 0; }
.${PANEL_CLASS} .clerk-md code { background: #f1f3f5; border-radius: 3px; padding: 0 3px; font-size: 12.5px; }
.${PANEL_CLASS} .clerk-md pre { background: #f6f8fa; padding: 6px 8px; overflow-x: auto; }
.${PANEL_CLASS} .clerk-md pre code { background: none; padding: 0; }
.${PANEL_CLASS} .clerk-md table { border-collapse: collapse; margin: 4px 0; font-size: 13px; }
.${PANEL_CLASS} .clerk-md th, .${PANEL_CLASS} .clerk-md td { border: 1px solid #d3d3d3; padding: 2px 6px; }
.${PANEL_CLASS} .clerk-md blockquote { border-left: 3px solid #d3d3d3; margin: 4px 0; padding-left: 8px; color: #555; }
.${PANEL_CLASS} .clerk-md hr { border: none; border-top: 1px solid #d3d3d3; margin: 8px 0; }
.${PANEL_CLASS} details > summary { cursor: pointer; }
.${PANEL_CLASS} .clerk-turn { margin-bottom: 10px; border-bottom: 1px solid #eef0f2; padding-bottom: 6px; }
.${PANEL_CLASS} .clerk-turn > summary { font-size: 14px; line-height: 1.35; white-space: pre-wrap; }
.${PANEL_CLASS} .clerk-fold > summary { font-size: 12px; color: #6c757d; margin: 4px 0 2px; }
.${PANEL_CLASS} .clerk-fold[open] { border-left: 2px solid #e3e6e9; padding-left: 8px; }
.${PANEL_CLASS} .clerk-button, .${PANEL_CLASS} .clerk-tool, .${PANEL_CLASS} .clerk-ask {
  font-family: inherit; font-weight: bold; text-transform: uppercase; letter-spacing: 0.02em;
  background: none; border: none; cursor: pointer; user-select: none; }
.${PANEL_CLASS} .clerk-button { font-size: 12px; color: #2c7fb8; margin: 4px 14px 0 0; padding: 2px 0; }
.${PANEL_CLASS} .clerk-tool { font-size: 11px; color: gray; margin-left: 12px; padding: 0; }
.${PANEL_CLASS} .clerk-ask { font-size: 12px; color: #2c7fb8; margin-left: 8px; padding: 0 6px; }
.${PANEL_CLASS} .clerk-button:hover, .${PANEL_CLASS} .clerk-tool:hover { color: #1a5a85; }
.${PANEL_CLASS} .clerk-ask:disabled { color: gray; cursor: default; }
.${PANEL_CLASS} .clerk-gene { color: #2c7fb8; cursor: pointer; border-bottom: 1px dotted currentColor; }
.${PANEL_CLASS} .clerk-gene:hover { border-bottom-style: solid; }
.${PANEL_CLASS} .clerk-gene.shown { background: #e3eef7; border-radius: 2px; }
.${PANEL_CLASS} .clerk-cluster, .${PANEL_CLASS} .clerk-genelist, .${PANEL_CLASS} a.clerk-view {
  color: #2c7fb8; cursor: pointer; border-bottom: 1px dotted currentColor; text-decoration: none; }
.${PANEL_CLASS} a.clerk-view { font-weight: bold; }
.${PANEL_CLASS} .clerk-cluster:hover, .${PANEL_CLASS} .clerk-genelist:hover,
.${PANEL_CLASS} a.clerk-view:hover { border-bottom-style: solid; }
.${PANEL_CLASS} .clerk-cluster.shown, .${PANEL_CLASS} a.clerk-view.shown { background: #e3eef7; border-radius: 2px; }
`;

// Model picker: aliases the `claude` CLI understands; '' = the CLI's default model.
const MODEL_OPTIONS = [
  ['', 'Default model'],
  ['opus', 'Opus'],
  ['sonnet', 'Sonnet'],
  ['haiku', 'Haiku'],
];

// Reasoning effort the `claude` CLI accepts (--effort); '' = the CLI's default.
const EFFORT_OPTIONS = [
  ['', 'Default effort'],
  ['low', 'Low effort'],
  ['medium', 'Medium effort'],
  ['high', 'High effort'],
  ['xhigh', 'Extra-high effort'],
  ['max', 'Max effort'],
];

/**
 * A <select> bound to a string model trait. A value set from Python that isn't one
 * of the choices (e.g. a full model id) is added rather than dropped.
 */
const make_trait_select = (model, trait, choices, title) => {
  const select = document.createElement('select');
  select.title = title;
  select.style.marginLeft = '5px';
  select.style.alignSelf = 'center';
  select.style.fontFamily = FONT;
  select.style.fontSize = '13px';
  const sync = () => {
    const current = model.get(trait) || '';
    const options = choices.some(([value]) => value === current)
      ? choices
      : [...choices, [current, current]];
    select.innerHTML = '';
    options.forEach(([value, label]) => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    });
    select.value = current;
  };
  select.addEventListener('change', () => {
    model.set(trait, select.value);
    model.save_changes();
  });
  return { select, sync };
};

/**
 * Celldega Clerk chat UI. Mirrors the Enrich widget's plumbing, but instead of
 * rendering enrichment bars it collects a free-form question, pre-gathers evidence
 * (gene list + Enrichr terms), and hands it to the Python side (which calls Claude).
 */
export const render_clerk = async ({ model, el }) => {
  // width 0 (or unset) => full width of the container (wide standalone panel).
  const rawWidth = model.get('width');
  const fullWidth = !rawWidth;
  const width = fullWidth ? null : rawWidth - 5;
  const height = model.get('height') || 450;

  const enrichrCache = {};
  let requestCounter = 0;

  // ---- layout ------------------------------------------------------------
  const container = document.createElement('div');
  container.className = PANEL_CLASS;
  container.style.width = fullWidth ? '100%' : `${width}px`;
  if (fullWidth) container.style.maxWidth = `${MAX_PANEL_WIDTH}px`;
  const style = document.createElement('style');
  style.textContent = MARKDOWN_CSS;
  container.appendChild(style);
  container.style.height = `${height}px`;
  container.style.marginLeft = '5px';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.fontFamily = FONT;

  const evidence = document.createElement('div');
  evidence.style.width = '100%';
  evidence.style.marginTop = '5px';
  evidence.style.padding = '6px';
  evidence.style.boxSizing = 'border-box';
  evidence.style.border = '1px solid #d3d3d3';
  evidence.style.maxHeight = '60px';
  evidence.style.overflowY = 'auto';

  const messagesPane = document.createElement('div');
  messagesPane.style.flex = '1 1 auto';
  messagesPane.style.marginTop = '5px';
  messagesPane.style.padding = '6px';
  messagesPane.style.boxSizing = 'border-box';
  messagesPane.style.border = '1px solid #d3d3d3';
  messagesPane.style.overflowY = 'auto';

  const inputRow = document.createElement('div');
  inputRow.style.display = 'flex';
  inputRow.style.marginTop = '5px';
  inputRow.style.marginBottom = '5px';

  const textarea = document.createElement('textarea');
  textarea.placeholder =
    'Ask about what you see (e.g. "What\'s in this field of view?")';
  textarea.rows = 2;
  textarea.style.flex = '1 1 auto';
  textarea.style.fontFamily = FONT;
  textarea.style.fontSize = '14px';
  textarea.style.padding = '5px';
  textarea.style.resize = 'vertical';

  const sendBtn = document.createElement('button');
  sendBtn.className = 'clerk-ask';
  sendBtn.textContent = 'Ask';

  // Both take effect on the next question and mirror the Python traits.
  const modelPicker = make_trait_select(
    model,
    'model',
    MODEL_OPTIONS,
    'Claude model for the next question ("Default model" = your claude CLI default)'
  );
  const effortPicker = make_trait_select(
    model,
    'effort',
    EFFORT_OPTIONS,
    'Reasoning effort for the next question; higher is slower and uses more tokens'
  );

  inputRow.appendChild(textarea);
  inputRow.appendChild(modelPicker.select);
  inputRow.appendChild(effortPicker.select);
  inputRow.appendChild(sendBtn);

  const toolbar = document.createElement('div');
  toolbar.style.display = 'flex';
  toolbar.style.justifyContent = 'flex-end';
  toolbar.style.marginTop = '4px';
  const tool = (text, title, onclick) => {
    const button = document.createElement('button');
    button.className = 'clerk-tool';
    button.textContent = text;
    button.title = title;
    button.addEventListener('click', onclick);
    toolbar.appendChild(button);
    return button;
  };

  container.appendChild(evidence);
  container.appendChild(toolbar);
  container.appendChild(messagesPane);
  container.appendChild(inputRow);
  el.appendChild(container);

  // Scrolling the conversation (or the gene strip) stops at its ends instead of
  // carrying on to scroll the notebook page, as in the other widgets.
  contain_scroll(messagesPane);
  contain_scroll(evidence);

  // ---- rendering helpers -------------------------------------------------
  // Screenshots appear in the conversation, under the question they were sent
  // with; the strip only shows the selected genes.
  const renderEvidence = () => {
    const genes = model.get('gene_list') || [];
    evidence.innerHTML = '';
    evidence.style.fontSize = '13px';
    evidence.textContent = genes.length
      ? `Selected genes (${genes.length}): ${genes.join(', ')}`
      : 'No genes selected. Each question also sends the linked views as they are.';
    // Make it visible when Clerk starts from earlier work (load_briefing).
    const briefing = model.get('briefing_label');
    if (briefing) {
      const line = document.createElement('div');
      line.style.color = '#8a5a00';
      line.title =
        'Clerk receives this earlier work with every question, as conclusions to check';
      line.textContent = briefing;
      evidence.appendChild(line);
    }
  };

  /** Screenshot + "Sent with: ..." line recorded on a question by Python. */
  const renderSentWith = (message, row) => {
    if (message.image) {
      const img = document.createElement('img');
      img.src = `data:image/png;base64,${message.image}`;
      img.style.display = 'block';
      img.style.maxWidth = '240px';
      img.style.maxHeight = '160px';
      img.style.marginTop = '4px';
      img.style.border = '1px solid #d3d3d3';
      img.title = 'Landscape view sent with this question';
      row.appendChild(img);
    }
    if (Array.isArray(message.evidence) && message.evidence.length) {
      const sent = document.createElement('div');
      sent.style.fontSize = '11.5px';
      sent.style.color = '#8a929b';
      sent.style.marginTop = '2px';
      sent.textContent = `Sent with: ${message.evidence.join(' · ')}`;
      row.appendChild(sent);
    }
  };

  // Which folds the scientist opened or closed, so re-rendering (each new message)
  // keeps them; keyed by turn and section.
  const folds = new Map();
  const make_fold = (key, label, default_open, className = 'clerk-fold') => {
    const details = document.createElement('details');
    details.className = className;
    details.open = folds.has(key) ? folds.get(key) : default_open;
    const summary = document.createElement('summary');
    summary.addEventListener('click', () => folds.set(key, !details.open));
    if (typeof label === 'string') summary.textContent = label;
    else summary.appendChild(label);
    details.appendChild(summary);
    return details;
  };

  const make_label = (text, color) => {
    const who = document.createElement('div');
    who.style.fontWeight = 'bold';
    who.style.fontSize = '11px';
    who.style.textTransform = 'uppercase';
    who.style.letterSpacing = '0.04em';
    who.style.color = color;
    who.textContent = text;
    return who;
  };

  // ---- evidence links ------------------------------------------------------
  // Everything Clerk cites can be clicked to replay it in the linked widgets right
  // away: genes (Landscape colors + Clustergram row), clusters (Landscape
  // highlight), gene lists in its work log, and views it defined ([Fig 1A]). The
  // scientist's own view is saved on the first click; "Back to your view" restores
  // it. These requests aren't blocked while Clerk is answering.
  const send_now = (fields) => {
    requestCounter += 1;
    model.set('request', { id: `${Date.now()}-${requestCounter}`, ...fields });
    model.save_changes();
  };

  // Hovering a gene shows its UniProt name and description, as in the other
  // widgets; clusters, gene lists and views get a short description.
  const gene_tooltip = make_gene_hover_tooltip();
  const html_tooltip = (html_for) => ({
    show: (key, event) => gene_tooltip.show_html(html_for(key), event),
    move: gene_tooltip.move,
    hide: gene_tooltip.hide,
  });
  const esc = (value) =>
    String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  const HINT_STYLE = 'color: #b8c4cf; font-size: 11px;';

  let shown_genes = [];
  let shown_clusters = [];
  let shown_view = '';
  const mark_shown = () => {
    messagesPane.querySelectorAll('.clerk-gene').forEach((link) => {
      link.classList.toggle('shown', shown_genes.includes(link.dataset.gene));
    });
    messagesPane.querySelectorAll('.clerk-cluster').forEach((link) => {
      link.classList.toggle(
        'shown',
        shown_clusters.includes(link.dataset.cluster)
      );
    });
    messagesPane.querySelectorAll('a.clerk-view').forEach((link) => {
      link.classList.toggle('shown', link.dataset.key === shown_view);
    });
  };
  // Click shows one item (clicking it again clears it); shift-click adds/removes.
  const toggle = (list, item, add) => {
    if (add) {
      return list.includes(item)
        ? list.filter((x) => x !== item)
        : [...list, item];
    }
    return list.length === 1 && list[0] === item ? [] : [item];
  };

  const show_genes = (genes, focus) => {
    shown_genes = genes;
    shown_clusters = [];
    shown_view = '';
    // The Clustergram zooms to the gene just clicked (if it's still shown).
    send_now({ show_genes: genes, focus: genes.includes(focus) ? focus : '' });
    mark_shown();
  };
  const show_gene = (gene, add) =>
    show_genes(toggle(shown_genes, gene, add), gene);
  const show_cluster = (cluster, add) => {
    shown_clusters = toggle(shown_clusters, cluster, add);
    shown_genes = [];
    shown_view = '';
    send_now({ show_clusters: shown_clusters });
    mark_shown();
  };

  const cluster_html = (cluster) => {
    const label = (model.get('cluster_labels') || {})[cluster];
    return (
      `<b>Cluster ${esc(cluster)}</b>${label ? `<br>${esc(label)}` : ''}` +
      `<br><span style="${HINT_STYLE}">Click: highlight in the Landscape · ` +
      `shift-click: add</span>`
    );
  };
  const describe_view = (view) => {
    const parts = [];
    const ls = view.landscape || {};
    if (ls.space) parts.push(`${ls.space} view`);
    if (ls.reset_view) parts.push('whole tissue');
    if (ls.zoom_to?.clusters) {
      parts.push(`zoom to cluster ${ls.zoom_to.clusters.join(', ')}`);
    }
    if (ls.zoom_to?.cells)
      parts.push(`zoom to ${ls.zoom_to.cells.length} cells`);
    if (ls.view) parts.push('a saved position');
    if (ls.clusters?.length) parts.push(`clusters ${ls.clusters.join(', ')}`);
    if (ls.genes?.length) parts.push(`genes ${ls.genes.join(', ')}`);
    const cg = view.clustergram || {};
    if (cg.marker_level !== undefined) {
      parts.push(`Clustergram: ${cg.marker_level} markers per cluster`);
    }
    if (cg.mode) parts.push(`Clustergram ${cg.mode}`);
    if (cg.focus_gene) parts.push(`Clustergram row ${cg.focus_gene}`);
    return parts.join(' · ');
  };
  const view_html = ([id, view]) =>
    `<b>${esc(view.caption || `View ${id}`)}</b><br>${esc(describe_view(view))}` +
    `<br><span style="${HINT_STYLE}">Click to show in the widgets</span>`;

  /** Link cited views ([Fig 1A](view:1A)) in rendered Markdown. */
  const link_views = (root, views, scope) => {
    root.querySelectorAll('a.clerk-view').forEach((link) => {
      const id = link.dataset.view;
      const view = views?.[id];
      if (!view) {
        link.replaceWith(document.createTextNode(link.textContent));
        return;
      }
      link.dataset.key = `${scope}:${id}`;
      const hover = html_tooltip(() => view_html([id, view]));
      link.addEventListener('mouseenter', (event) => hover.show(id, event));
      link.addEventListener('mousemove', hover.move);
      link.addEventListener('mouseleave', hover.hide);
      link.addEventListener('click', (event) => {
        event.preventDefault();
        hover.hide();
        shown_view = link.dataset.key;
        shown_genes = view.landscape?.genes || [];
        shown_clusters = view.landscape?.genes?.length
          ? []
          : view.landscape?.clusters || [];
        send_now({
          apply_view: {
            landscape: view.landscape,
            clustergram: view.clustergram,
          },
        });
        mark_shown();
      });
    });
  };

  /** Genes, clusters and cited views in rendered text become links. */
  const add_links = (root, { genes = [], views = null, scope = '' } = {}) => {
    link_genes(root, genes, show_gene, gene_tooltip);
    link_clusters(
      root,
      model.get('cluster_names') || [],
      show_cluster,
      html_tooltip(cluster_html)
    );
    if (views !== undefined) link_views(root, views, scope);
  };

  /** "16 genes" in a work line: hover lists them, click shows them all. */
  const link_gene_count = (root, genes) => {
    if (!genes?.length) return;
    const walker = document.createTreeWalker(root, 4);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      const match = /\b(\d+) genes\b/.exec(node.nodeValue);
      if (!match || Number(match[1]) !== genes.length) return;
      const span = document.createElement('span');
      span.className = 'clerk-genelist';
      span.textContent = match[0];
      span.tabIndex = 0;
      span.setAttribute('role', 'button');
      const shown = genes.slice(0, MAX_SHOWN_GENES);
      const hover = html_tooltip(
        () =>
          `<b>${genes.length} genes</b><br>${esc(genes.join(', '))}` +
          `<br><span style="${HINT_STYLE}">Click to show ${
            genes.length > shown.length ? `the first ${shown.length}` : 'them'
          } in the Landscape</span>`
      );
      span.addEventListener('mouseenter', (event) => hover.show('', event));
      span.addEventListener('mousemove', hover.move);
      span.addEventListener('mouseleave', hover.hide);
      span.addEventListener('click', () => {
        hover.hide();
        show_genes(shown, shown[0]);
      });
      const after = node.splitText(match.index);
      after.nodeValue = after.nodeValue.slice(match[0].length);
      node.parentNode.insertBefore(span, after);
    });
  };

  const action_line = (message) => {
    // A lookup or view change Clerk made (e.g. "Changed the Clustergram: ..."), or a
    // note from the panel itself (e.g. where an export was saved).
    const note = document.createElement('div');
    note.style.margin = '2px 0';
    note.style.fontSize = '12px';
    if (message.role === 'note') {
      note.style.color = '#6c757d';
      note.textContent = message.content || '';
    } else {
      note.style.fontStyle = 'italic';
      note.style.color = '#2c7fb8';
      note.textContent = `↻ ${message.content || ''}`;
      link_gene_count(note, message.genes);
      add_links(note, { genes: message.genes });
    }
    return note;
  };
  const is_line = (message) =>
    message.role === 'action' || message.role === 'note';

  // Answers are Markdown; render_markdown escapes all text before adding its own
  // markup, so model output can't inject HTML.
  const markdown = (text, links = {}) => {
    const body = document.createElement('div');
    body.className = 'clerk-md';
    body.style.fontSize = '14px';
    body.style.lineHeight = '1.35';
    body.innerHTML = render_markdown(text || '');
    add_links(body, { views: null, ...links });
    return body;
  };

  const send_request = (fields) => {
    if (model.get('pending')) return;
    requestCounter += 1;
    model.set('request', { id: `${Date.now()}-${requestCounter}`, ...fields });
    model.save_changes();
  };

  const make_button = (text, title, onclick) => {
    const button = document.createElement('button');
    button.className = 'clerk-button';
    button.textContent = text;
    button.title = title;
    button.addEventListener('click', onclick);
    return button;
  };

  const renderTurn = (turn, index, is_last) => {
    const key = `turn-${index}`;
    let wrapper;
    if (turn.question) {
      const label = document.createElement('span');
      const you = document.createElement('span');
      you.style.fontWeight = 'bold';
      you.style.fontSize = '11px';
      you.style.letterSpacing = '0.04em';
      you.style.color = '#47515b';
      you.textContent = 'YOU  ';
      label.appendChild(you);
      label.appendChild(document.createTextNode(turn.question.content || ''));
      wrapper = make_fold(key, label, true, 'clerk-turn');
      renderSentWith(turn.question, wrapper);
    } else {
      wrapper = document.createElement('div');
      wrapper.className = 'clerk-turn';
    }

    if (turn.work.length) {
      const steps = turn.work.length;
      const work = make_fold(
        `${key}-work`,
        `Work · ${steps} step${steps === 1 ? '' : 's'}`,
        turn.pending
      );
      turn.work.forEach((message, step) => {
        if (is_line(message)) work.appendChild(action_line(message));
        else {
          const interim = markdown(message.content, {
            genes: message.genes,
            views: message.views,
            scope: `${key}-work-${step}`,
          });
          interim.style.color = '#47515b';
          interim.style.fontSize = '13px';
          work.appendChild(interim);
        }
      });
      wrapper.appendChild(work);
    }

    let asked = false;
    if (turn.answer) {
      const answer = document.createElement('div');
      answer.style.marginTop = '4px';
      answer.appendChild(make_label('Clerk', '#2c7fb8'));
      const {
        main,
        evidence: detail,
        after,
      } = split_evidence(turn.answer.content);
      const links = {
        genes: turn.answer.genes || [],
        views: turn.answer.views,
        scope: key,
      };
      if (main) answer.appendChild(markdown(main, links));
      if (detail) {
        const fold = make_fold(`${key}-evidence`, 'Evidence', false);
        fold.appendChild(markdown(detail, links));
        answer.appendChild(fold);
      }
      if (after) answer.appendChild(markdown(after, links));
      asked = asks_question(after || main || turn.answer.content);
      wrapper.appendChild(answer);
    }
    turn.results.forEach((message) => {
      if (is_line(message)) wrapper.appendChild(action_line(message));
      else
        wrapper.appendChild(
          markdown(message.content, { genes: message.genes })
        );
    });
    turn.errors.forEach((message) => {
      const row = document.createElement('div');
      row.style.marginTop = '4px';
      row.style.color = '#c0392b';
      row.appendChild(make_label('Clerk (error)', '#c0392b'));
      const body = document.createElement('div');
      body.style.whiteSpace = 'pre-wrap';
      body.style.fontSize = '14px';
      body.textContent = message.content || '';
      row.appendChild(body);
      wrapper.appendChild(row);
    });

    const idle = !model.get('pending');
    if (turn.pause && idle) {
      const row = document.createElement('div');
      row.style.marginTop = '4px';
      row.style.fontSize = '13px';
      row.style.color = '#8a5a00';
      row.textContent = turn.pause.content || 'Clerk paused.';
      row.appendChild(document.createElement('br'));
      row.appendChild(
        make_button('Continue', 'Let Clerk keep going on this question', () =>
          send_request({ continue: true })
        )
      );
      wrapper.appendChild(row);
    } else if (is_last && asked && idle && !turn.errors.length) {
      wrapper.appendChild(
        make_button('Yes', "Answer Clerk's question with yes", () =>
          send_request({ question: 'Yes' })
        )
      );
      wrapper.appendChild(
        make_button('No', "Answer Clerk's question with no", () =>
          send_request({ question: 'No' })
        )
      );
    }

    if (turn.pending) {
      const spinner = document.createElement('div');
      spinner.style.color = '#2c7fb8';
      spinner.style.fontSize = '13px';
      spinner.style.marginTop = '4px';
      spinner.textContent = 'Clerk is working…';
      wrapper.appendChild(spinner);
    }
    return wrapper;
  };

  const renderMessages = () => {
    const messages = model.get('messages') || [];
    const pending = model.get('pending');
    messagesPane.innerHTML = '';

    if (!messages.length && !pending) {
      const empty = document.createElement('div');
      empty.style.color = '#8a929b';
      empty.style.fontSize = '13px';
      empty.textContent =
        'Ask Clerk a question to interpret this cluster or region.';
      messagesPane.appendChild(empty);
    }

    const turns = group_turns(messages, pending);
    turns.forEach((turn, index) => {
      messagesPane.appendChild(
        renderTurn(turn, index, index === turns.length - 1)
      );
    });

    mark_shown();
    messagesPane.scrollTop = messagesPane.scrollHeight;
  };

  // Open or close every fold at once, e.g. to search the whole conversation.
  const set_all_folds = (open) => {
    messagesPane.querySelectorAll('details').forEach((details) => {
      details.open = open;
    });
    group_turns(model.get('messages') || []).forEach((_turn, index) => {
      ['', '-work', '-evidence'].forEach((suffix) =>
        folds.set(`turn-${index}${suffix}`, open)
      );
    });
  };

  const setBusy = (busy) => {
    sendBtn.disabled = busy;
    textarea.disabled = busy;
    sendBtn.textContent = busy ? '…' : 'Ask';
  };

  // ---- fetch Enrichr evidence (reuses the existing Enrichr API) -----------
  const fetchEnrichrTerms = async (genes) => {
    if (!genes || !genes.length) return [];
    const cacheKey = genes.join(',');
    if (enrichrCache[cacheKey]) return enrichrCache[cacheKey];
    try {
      const { userListId } = await postGeneList(genes, null);
      const data = await fetchEnrichment(userListId, ENRICHR_LIB);
      const terms = (data[ENRICHR_LIB] || [])
        .map((d) => ({ name: d[1], score: d[4], genes: d[5] }))
        .sort((a, b) => b.score - a.score)
        .slice(0, ENRICHR_TERMS);
      enrichrCache[cacheKey] = terms;
      return terms;
    } catch (error) {
      // Enrichr is best-effort evidence; proceed without it on failure.
      handleAsyncError(error, { context: 'clerk fetchEnrichrTerms' });
      return [];
    }
  };

  // ---- ask flow ----------------------------------------------------------
  const submit = async () => {
    const question = textarea.value.trim();
    if (!question || model.get('pending')) return;

    setBusy(true);
    textarea.value = '';

    const genes = model.get('gene_list') || [];
    // With an Enrich panel linked, Clerk reads that panel's results instead.
    const enrichr_terms =
      model.get('fetch_enrichr') === false
        ? []
        : await fetchEnrichrTerms(genes);

    requestCounter += 1;
    const id = `${Date.now()}-${requestCounter}`;
    model.set('request', {
      id,
      question,
      gene_list: genes,
      enrichr_terms,
    });
    model.save_changes();
  };

  // Shown once evidence links have changed the views; restores the view the
  // scientist had before following them.
  const back = tool(
    'Back to your view',
    'Restore the Landscape and Clustergram as they were before you followed links',
    () => {
      shown_genes = [];
      shown_clusters = [];
      shown_view = '';
      send_now({ restore_view: true });
      mark_shown();
    }
  );
  back.style.color = '#2c7fb8';
  back.style.marginRight = 'auto';
  back.style.marginLeft = '0';
  const sync_back = () => {
    back.style.display = model.get('can_restore') ? '' : 'none';
  };
  toolbar.insertBefore(back, toolbar.firstChild);

  tool('Expand all', 'Open every turn, work log and evidence section', () =>
    set_all_folds(true)
  );
  tool('Collapse all', 'Close every turn', () => set_all_folds(false));
  tool(
    'Export',
    'Save this conversation as an HTML report with its screenshots, the state to ' +
      'reproduce them, and the recorded cell types (written next to the notebook)',
    () => send_request({ export: true })
  );

  sendBtn.addEventListener('click', submit);
  textarea.addEventListener('keydown', (e) => {
    // Enter to send, Shift+Enter for newline.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  });

  // ---- traitlet listeners ------------------------------------------------
  const onPending = () => {
    renderMessages();
    setBusy(!!model.get('pending'));
  };
  const listeners = [
    ['change:gene_list', renderEvidence],
    ['change:briefing_label', renderEvidence],
    ['change:cluster_names', renderMessages],
    ['change:cluster_labels', renderMessages],
    ['change:can_restore', () => sync_back()],
    ['change:messages', renderMessages],
    ['change:pending', onPending],
    ['change:model', modelPicker.sync],
    ['change:effort', effortPicker.sync],
  ];
  listeners.forEach(([event, handler]) => model.on(event, handler));

  modelPicker.sync();
  effortPicker.sync();
  sync_back();
  renderEvidence();
  renderMessages();

  return {
    finalize: () => {
      gene_tooltip.destroy();
      listeners.forEach(([event, handler]) => model.off?.(event, handler));
      el.innerHTML = '';
    },
  };
};
