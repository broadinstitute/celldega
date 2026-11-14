import { postGeneList, fetchEnrichment } from '../external_apis/enrichr_api';
import { handleAsyncError } from '../temp_utils/errorHandler';
import { contain_scroll, make_gene_hover_tooltip } from '../ui/gene_info';
import { render_markdown } from '../ui/markdown';

import { render_enrichment } from './clerk_enrichment';
import {
  asks_question,
  group_turns,
  link_clusters,
  link_genes,
  split_evidence,
} from './clerk_turns';

const FONT =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';
// Clerk's own words (answers, interim replies, evidence) in a serif, set apart from
// the scientist's questions and the panel's controls.
const CLERK_SERIF =
  'ui-serif, "Iowan Old Style", Charter, Georgia, Cambria, "Times New Roman", serif';

// Library used to pre-gather Enrichr evidence that rides along in the prompt.
const ENRICHR_LIB = 'CellMarker_2024';
// Terms per library fetched for an Enrichr chart (Clerk itself reads the top few).
const ENRICHR_CARD_TERMS = 20;

// Most genes one click shows (the Landscape's gene search allows 20).
const MAX_SHOWN_GENES = 20;

// A full-width panel is capped here so chat text stays readable.
const MAX_PANEL_WIDTH = 900;

// Below this width (px) the question box takes its own line.
const NARROW_PANEL_WIDTH = 480;

// Styles for rendered Markdown, scoped to the panel's class so they can't leak into
// the rest of the notebook.
const PANEL_CLASS = 'celldega-clerk';
const MARKDOWN_CSS = `
.${PANEL_CLASS} .clerk-md { font-family: ${CLERK_SERIF}; }
.${PANEL_CLASS} .clerk-md code, .${PANEL_CLASS} .clerk-md pre { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.${PANEL_CLASS} .clerk-md p { margin: 5px 0; }
.${PANEL_CLASS} .clerk-md a { color: #2c7fb8; }
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
.${PANEL_CLASS} .clerk-turn { margin-bottom: 16px; border-bottom: 1px solid #eef0f2; padding-bottom: 10px; }
.${PANEL_CLASS} .clerk-turn > summary { font-size: 14px; line-height: 1.35; white-space: pre-wrap; }
.${PANEL_CLASS} .clerk-fold > summary { font-size: 12px; color: #6c757d; margin: 4px 0 2px; }
.${PANEL_CLASS} .clerk-fold[open] { border-left: 2px solid #e3e6e9; padding-left: 8px; }
.${PANEL_CLASS} .clerk-button, .${PANEL_CLASS} .clerk-tool, .${PANEL_CLASS} .clerk-ask {
  font-family: inherit; font-weight: bold; text-transform: uppercase; letter-spacing: 0.02em;
  background: none; border: none; cursor: pointer; user-select: none; }
.${PANEL_CLASS} .clerk-button { font-size: 12px; color: #2c7fb8; margin: 4px 14px 0 0; padding: 2px 0; }
.${PANEL_CLASS} .clerk-tool { font-size: 9px; color: gray; margin-left: 9px; padding: 0; }
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
.${PANEL_CLASS} .clerk-enrichment { margin: 4px 0 6px; padding: 5px; border: 1px solid #d3d3d3; }
.${PANEL_CLASS} .clerk-enrichment-title { font-size: 11px; font-weight: bold; letter-spacing: 0.04em;
  text-transform: uppercase; color: #47515b; margin-bottom: 3px; }
.${PANEL_CLASS} .clerk-enrichment-library { display: block; max-width: 100%; margin-bottom: 4px;
  font-family: inherit; font-size: 12px; }
.${PANEL_CLASS} .clerk-enrichment-bars { max-height: 176px; overflow-y: auto; border: 1px solid #d3d3d3;
  font-size: 13px; }
.${PANEL_CLASS} .clerk-enrichment-bar { position: relative; height: 21px; margin-bottom: 1px; cursor: pointer;
  user-select: none; }
.${PANEL_CLASS} .clerk-enrichment-fill { position: absolute; top: 0; bottom: 0; left: 0;
  background: steelblue; opacity: 0.25; }
.${PANEL_CLASS} .clerk-enrichment-bar:hover .clerk-enrichment-fill { opacity: 0.45; }
.${PANEL_CLASS} .clerk-enrichment-term { position: relative; display: block; padding: 0 5px; font-size: 13px;
  line-height: 20px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.${PANEL_CLASS} .clerk-enrichment-bar.dimmed .clerk-enrichment-term { color: gray; }
.${PANEL_CLASS} .clerk-enrichment-bar.selected .clerk-enrichment-term { font-weight: bold; }
.${PANEL_CLASS} .clerk-enrichment-genes { margin-top: 5px; padding: 3px; border: 1px solid #d3d3d3;
  max-height: 96px; overflow-y: auto; font-size: 12px; line-height: 1.35; }
/* Gene colors as in the Enrich panel: black, then blue (in the selected term) or
   dark gray (not in it); the gene shown in the views is bold. */
.${PANEL_CLASS} .clerk-enrichment-genes .clerk-gene { color: black; font-weight: 550; border-bottom: none; }
.${PANEL_CLASS} .clerk-enrichment-genes .clerk-gene:hover { text-decoration: underline; }
.${PANEL_CLASS} .clerk-enrichment-genes .clerk-gene.in-term { color: blue; }
.${PANEL_CLASS} .clerk-enrichment-genes .clerk-gene.out-term { color: #2F4F4F; }
.${PANEL_CLASS} .clerk-enrichment-genes .clerk-gene.shown { font-weight: bold; background: none; }
.${PANEL_CLASS} .clerk-enrichment-link { display: block; margin-top: 4px; font-size: 12px; color: #2f74ff; }
.${PANEL_CLASS} .clerk-figure > summary { color: #2c7fb8; }
.${PANEL_CLASS} .clerk-image-view { display: block; width: fit-content; margin-top: 3px; font-size: 11px; color: #2c7fb8; }
.${PANEL_CLASS} .clerk-sent-images { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.${PANEL_CLASS} .clerk-shown { margin-top: 8px; }
.${PANEL_CLASS} .clerk-shown-caption { font-size: 12px; font-style: italic; color: #2c7fb8; }
.${PANEL_CLASS} .clerk-sent-image { flex: 0 1 auto; min-width: 100px; max-width: 240px; }
.${PANEL_CLASS} .clerk-sent-images > .clerk-sent-image:nth-last-child(2),
.${PANEL_CLASS} .clerk-sent-images > .clerk-sent-image:nth-last-child(2) ~ .clerk-sent-image {
  max-width: calc(50% - 3px); }
.${PANEL_CLASS} .clerk-sent-image img { display: block; max-width: 100%; max-height: 160px;
  border: 1px solid #d3d3d3; }
.${PANEL_CLASS} .clerk-report-form { margin-top: 5px; padding: 6px; border: 1px solid #d3d3d3; }
.${PANEL_CLASS} .clerk-report-form label { display: block; font-size: 12px; color: #47515b; }
.${PANEL_CLASS} .clerk-report-form input { width: 100%; box-sizing: border-box; margin-top: 3px; padding: 4px; font: inherit; font-size: 13px; }
.${PANEL_CLASS} .clerk-recorded { white-space: pre-wrap; font-size: 13px; color: #47515b; margin: 4px 0; }
.${PANEL_CLASS} .clerk-offer { font-size: 12px; color: #47515b; margin: 2px 0 4px; }
.${PANEL_CLASS} .clerk-offer .clerk-button { font-size: 11px; margin: 0 0 0 8px; }
.${PANEL_CLASS} .clerk-analysis { margin: 2px 0 6px 14px; }
.${PANEL_CLASS} .clerk-analysis-path { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px; color: #47515b; overflow-wrap: anywhere; user-select: all; }
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

  // A briefing Clerk started from, if any, stays visible above the conversation.
  const evidence = document.createElement('div');
  evidence.className = 'clerk-evidence';
  evidence.style.width = '100%';
  evidence.style.boxSizing = 'border-box';

  const messagesPane = document.createElement('div');
  messagesPane.style.flex = '1 1 auto';
  messagesPane.style.marginTop = '5px';
  messagesPane.style.padding = '6px';
  messagesPane.style.boxSizing = 'border-box';
  messagesPane.style.border = '1px solid #d3d3d3';
  messagesPane.style.overflowY = 'auto';

  const inputRow = document.createElement('div');
  inputRow.style.display = 'flex';
  // In a narrow sidecar the pickers and Ask wrap under the question box.
  inputRow.style.flexWrap = 'wrap';
  inputRow.style.alignItems = 'center';
  inputRow.style.rowGap = '4px';
  inputRow.style.marginTop = '5px';
  inputRow.style.marginBottom = '5px';

  const textarea = document.createElement('textarea');
  textarea.placeholder =
    'Ask about what you see (e.g. "What\'s in this field of view?")';
  textarea.rows = 2;
  textarea.style.flex = '1 1 auto';
  textarea.style.minWidth = '220px';
  // A narrow panel (a sidecar) gives the question its own line, pickers below. A
  // sidecar sizes itself to the row, so this follows the panel's actual width.
  const fit_input = (panel_width) => {
    textarea.style.flexBasis =
      panel_width > 0 && panel_width < NARROW_PANEL_WIDTH ? '100%' : '';
  };
  fit_input(fullWidth ? 0 : width);
  const resize_observer =
    typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(([entry]) => fit_input(entry.contentRect.width));
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
  toolbar.style.flexWrap = 'wrap';
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

  // Scrolling the conversation stops at its ends instead of carrying on to scroll
  // the notebook page, as in the other widgets.
  contain_scroll(messagesPane);

  // ---- rendering helpers -------------------------------------------------
  // Screenshots appear under the question they were sent with. Their saved views
  // let the scientist revisit the evidence after navigating elsewhere.
  /**
   * Screenshots + "Sent with: ..." line recorded on a question by Python: the
   * Landscape, Clustergram and Yearbook as Clerk saw them, side by side, each with
   * a link back to that view (and one to all of them).
   */
  const renderSentWith = (message, row, on_snapshot) => {
    const shots = [
      ['landscape', message.image, 'Landscape'],
      ['clustergram', message.clustergram_image, 'Clustergram'],
      ['yearbook', message.yearbook_image, 'Yearbook'],
    ].filter(([, image]) => image);
    const snapshots = message.snapshots || {};
    const view_link = (text, title, which) => {
      const link = document.createElement('a');
      link.className = 'clerk-image-view';
      link.href = '#';
      link.textContent = text;
      link.title = title;
      link.addEventListener('click', (event) => {
        event.preventDefault();
        on_snapshot(which);
      });
      return link;
    };
    if (shots.length) {
      const strip = document.createElement('div');
      strip.className = 'clerk-sent-images';
      shots.forEach(([name, image, label]) => {
        const figure = document.createElement('div');
        figure.className = 'clerk-sent-image';
        const img = document.createElement('img');
        img.src = `data:image/png;base64,${image}`;
        img.title =
          message.role === 'view'
            ? `${label} view Clerk showed`
            : `${label} view sent with this question`;
        figure.appendChild(img);
        if (snapshots[name]) {
          figure.appendChild(
            view_link(
              'Show this view',
              `Return the ${label} to this view; RETURN takes you back`,
              { [name]: snapshots[name] }
            )
          );
        }
        strip.appendChild(figure);
      });
      row.appendChild(strip);
      const saved = Object.keys(snapshots).filter((name) => snapshots[name]);
      if (saved.length > 1) {
        row.appendChild(
          view_link(
            saved.length === 2 ? 'Show both views' : 'Show all views',
            'Return the linked views to those sent with this question',
            snapshots
          )
        );
      }
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

  const make_button = (text, title, onclick) => {
    const button = document.createElement('button');
    button.className = 'clerk-button';
    button.textContent = text;
    button.title = title;
    button.addEventListener('click', onclick);
    return button;
  };

  // ---- fetch Enrichr evidence (reuses the existing Enrichr API) -----------
  // One upload per gene list, then one request per library, all cached.
  const enrichr_list = (genes) => {
    const key = genes.join(',');
    if (!enrichrCache[key]) {
      enrichrCache[key] = { list: postGeneList(genes, null), terms: {} };
      enrichrCache[key].list.catch(() => delete enrichrCache[key]);
    }
    return enrichrCache[key];
  };
  /** Top terms of one library for a gene list, and its Enrichr web page. */
  const fetch_terms = async (genes, library) => {
    const entry = enrichr_list(genes);
    const { userListId, shortId } = await entry.list;
    if (!entry.terms[library]) {
      entry.terms[library] = fetchEnrichment(userListId, library).then((data) =>
        (data?.[library] || [])
          .map((d) => ({
            name: d[1],
            score: d[4],
            genes: d[5],
            adjusted_p: d[6],
            odds_ratio: d[3],
          }))
          .sort((a, b) => b.score - a.score)
          .slice(0, ENRICHR_CARD_TERMS)
      );
      entry.terms[library].catch(() => delete entry.terms[library]);
    }
    const terms = await entry.terms[library];
    return {
      terms,
      short_id: shortId || '',
      url: shortId
        ? `https://maayanlab.cloud/Enrichr/enrich?dataset=${shortId}`
        : '',
    };
  };
  const fetchEnrichrTerms = async (genes) => {
    if (!genes || !genes.length) return { terms: [], short_id: '' };
    try {
      return await fetch_terms(genes, ENRICHR_LIB);
    } catch (error) {
      // Enrichr is best-effort evidence; proceed without it on failure.
      handleAsyncError(error, { context: 'clerk fetchEnrichrTerms' });
      return { terms: [], short_id: '' };
    }
  };

  // ---- evidence links ------------------------------------------------------
  // Everything Clerk cites can be clicked to replay it in the linked widgets right
  // away: genes (Landscape colors + Clustergram row), clusters (Landscape
  // highlight), gene lists in its work log, and views it defined ([Fig 1A]). The
  // scientist's own view is saved on the first click; RETURN restores
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
  // What an Enrichr chart needs from the panel (see clerk_enrichment.js). Its bars
  // scroll under the conversation's own containment, which passes the gesture on
  // to the conversation at their ends.
  const enrichment_handlers = {
    on_gene: show_gene,
    on_genes: (genes) => show_genes(genes.slice(0, MAX_SHOWN_GENES), genes[0]),
    tooltip: gene_tooltip,
    esc,
    fetch_terms,
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
    const group = cg.selection?.dendrogram;
    if (group) {
      const which = group.name
        ? `group ${group.name}`
        : `group of ${group.members?.length || 0}`;
      parts.push(
        `Clustergram ${group.axis === 'row' ? 'row' : 'column'} dendrogram ${which}`
      );
    }
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
        // Keep its text, and any gene or cluster links inside it.
        link.replaceWith(...link.childNodes);
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

  // An analysis notebook Clerk drafted: where it is, and running it with Claude
  // Code (in a separate process) once the scientist has had a look. Clerk never
  // runs it.
  const analysis_line = (note, analysis) => {
    const wrapper = document.createElement('div');
    wrapper.appendChild(note);
    const box = document.createElement('div');
    box.className = 'clerk-analysis';
    const where = document.createElement('div');
    where.className = 'clerk-analysis-path';
    where.textContent = analysis.path || '';
    where.title = 'Open it in Jupyter to inspect, edit or run it yourself';
    box.appendChild(where);
    const status = document.createElement('div');
    status.className = 'clerk-offer';
    const { status: state = 'drafted' } = analysis;
    if (state === 'running') {
      status.textContent = 'Claude Code is running it…';
    } else if (state === 'done' || state === 'failed') {
      status.textContent =
        state === 'done'
          ? 'Claude Code ran it; the notebook now has its outputs.'
          : "Claude Code couldn't run it.";
      if (analysis.summary) {
        const fold = document.createElement('details');
        fold.className = 'clerk-fold';
        const summary = document.createElement('summary');
        summary.textContent = "Claude Code's summary";
        const text = document.createElement('div');
        text.className = 'clerk-recorded';
        text.textContent = analysis.summary;
        fold.append(summary, text);
        box.appendChild(status);
        box.appendChild(fold);
        status.dataset.done = '1';
      }
    } else {
      status.textContent = 'Inspect it before running it.';
    }
    if (!status.dataset.done) box.appendChild(status);
    if (state === 'drafted' || state === 'failed') {
      const run = make_button(
        state === 'failed'
          ? 'Run again with Claude Code'
          : 'Run with Claude Code',
        'Claude Code runs the notebook in a separate process (and may fix small ' +
          'errors in it); its summary comes back here for Clerk to interpret',
        () => {
          run.disabled = true;
          model.send?.({ event: 'run_analysis', id: analysis.id });
        }
      );
      status.appendChild(run);
    }
    wrapper.appendChild(box);
    return wrapper;
  };

  // A notebook Clerk suggested (rather than one the scientist asked for): written
  // only when the scientist clicks Draft notebook.
  const notebook_offer_line = (note, offer) => {
    const wrapper = document.createElement('div');
    wrapper.appendChild(note);
    const box = document.createElement('div');
    box.className = 'clerk-analysis';
    if (offer.purpose) {
      const what = document.createElement('div');
      what.className = 'clerk-recorded';
      what.textContent = offer.purpose;
      box.appendChild(what);
    }
    if (!model.get('pending')) {
      const ask = document.createElement('div');
      ask.className = 'clerk-offer';
      ask.textContent = 'Draft this notebook for you to inspect?';
      const yes = make_button(
        'Draft notebook',
        'Write the notebook under clerk_files/analyses; nothing runs until you choose to',
        () => {
          yes.disabled = true;
          model.send?.({ event: 'draft_notebook', id: offer.id });
        }
      );
      ask.appendChild(yes);
      box.appendChild(ask);
    }
    wrapper.appendChild(box);
    return wrapper;
  };

  const action_line = (message) => {
    // A lookup or view change Clerk made (e.g. "Changed the Clustergram: ..."), or a
    // note from the panel itself (e.g. where an export was saved). A line's details
    // (e.g. each cluster's recorded cell type) are in its turn's Evidence.
    const note = document.createElement('div');
    note.style.margin = '2px 0';
    note.style.fontSize = '12px';
    if (message.role === 'note') {
      note.style.color = '#6c757d';
      note.textContent = message.content || '';
      return note;
    }
    note.style.fontStyle = 'italic';
    note.style.color = '#2c7fb8';
    note.textContent = `↻ ${message.content || ''}`;
    if (message.detail) note.title = message.detail;
    link_gene_count(note, message.genes);
    add_links(note, { genes: message.genes });
    if (message.analysis) return analysis_line(note, message.analysis);
    if (message.notebook_offer?.status === 'offered')
      return notebook_offer_line(note, message.notebook_offer);
    const offer = message.label_offer;
    if (!offer) return note;
    // Recorded cell types: label the Clustergram with them only if the scientist
    // says so.
    const wrapper = document.createElement('div');
    wrapper.appendChild(note);
    if (offer.status === 'done') {
      const done = document.createElement('div');
      done.style.margin = '2px 0';
      done.style.fontSize = '12px';
      done.style.fontStyle = 'italic';
      done.style.color = '#2c7fb8';
      done.textContent = `↻ ${offer.result || 'Labeled the Clustergram'}`;
      if (offer.result_detail) done.title = offer.result_detail;
      wrapper.appendChild(done);
    } else if (!model.get('pending')) {
      const ask = document.createElement('div');
      ask.className = 'clerk-offer';
      // Names the manual column category the labels go in, e.g. "(cell_type)".
      ask.textContent = `Label these clusters in the Clustergram${
        offer.attribute ? ` (${offer.attribute})` : ''
      }?`;
      const yes = make_button(
        'Label',
        'Show these cell types as tentative Clustergram column labels, and mark ' +
          'their marker genes on the rows (your own labels are kept)',
        () => {
          yes.disabled = true;
          model.send?.({ event: 'label_clustergram', id: offer.id });
        }
      );
      ask.appendChild(yes);
      wrapper.appendChild(ask);
    }
    return wrapper;
  };
  /** Details of a turn's lines (cell types recorded, labels applied), for Evidence. */
  const line_details = (messages) =>
    messages
      .filter((m) => m.role === 'action')
      .flatMap((m) => [m.detail, m.label_offer?.result_detail])
      .filter(Boolean);
  const is_line = (message) =>
    message.role === 'action' || message.role === 'note';

  // Answers are Markdown; render_markdown escapes all text before adding its own
  // markup, so model output can't inject HTML.
  // "[MYH11]" without a link target: the brackets would show. Gene and cluster
  // names are linked anyway, so drop them (figure links, "[Fig 1A](view:1A)", stay).
  const unbracket = (text, genes = []) => {
    const known = new Set(
      [...genes, ...(model.get('cluster_names') || [])].map((name) =>
        String(name).toUpperCase()
      )
    );
    return String(text || '').replace(
      /\[([A-Za-z0-9][A-Za-z0-9._/-]*)\](?!\()/g,
      (whole, name) => (known.has(name.toUpperCase()) ? name : whole)
    );
  };

  const markdown = (text, links = {}) => {
    const body = document.createElement('div');
    body.className = 'clerk-md';
    body.style.fontSize = '15px';
    body.style.lineHeight = '1.45';
    body.innerHTML = render_markdown(unbracket(text, links.genes));
    add_links(body, { views: null, ...links });
    return body;
  };

  const send_request = (fields) => {
    if (model.get('pending')) return;
    requestCounter += 1;
    model.set('request', { id: `${Date.now()}-${requestCounter}`, ...fields });
    model.save_changes();
  };

  // A preview's "Show this view": open its saved views in the linked widgets.
  const open_snapshots = (snapshots) => {
    shown_genes = [];
    shown_clusters = [];
    shown_view = '';
    send_now({ show_snapshot: snapshots });
    mark_shown();
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
      renderSentWith(turn.question, wrapper, open_snapshots);
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
    // Views Clerk changed for this question, as Snapshots to return to.
    turn.shown.forEach((message) => {
      const shown = document.createElement('div');
      shown.className = 'clerk-shown';
      const caption = document.createElement('div');
      caption.className = 'clerk-shown-caption';
      caption.textContent = `Clerk showed: ${message.content || 'a view'}`;
      shown.appendChild(caption);
      renderSentWith(message, shown, open_snapshots);
      wrapper.appendChild(shown);
    });

    let asked = false;
    if (turn.answer) {
      const answer = document.createElement('div');
      // Room between the question (and its work) and Clerk's answer.
      answer.style.marginTop = '12px';
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
      const recorded = line_details([...turn.work, ...turn.results]);
      if (detail || recorded.length) {
        const fold = make_fold(`${key}-evidence`, 'Evidence', false);
        if (detail) fold.appendChild(markdown(detail, links));
        recorded.forEach((text) => {
          const line = document.createElement('div');
          line.className = 'clerk-recorded';
          line.textContent = text;
          add_links(line, { genes: links.genes });
          fold.appendChild(line);
        });
        answer.appendChild(fold);
      }
      if (after) answer.appendChild(markdown(after, links));
      asked = asks_question(after || main || turn.answer.content);
      wrapper.appendChild(answer);
    }
    // Enrichr results, under the answer (or as they arrive while Clerk works), each
    // folded under its title, e.g. "Enrichr · Cluster 4 upregulated".
    turn.figures.forEach((message, figure) => {
      const fold = make_fold(
        `${key}-enrichr-${figure}`,
        `Enrichr · ${message.title || message.label || 'genes'}`,
        false,
        'clerk-fold clerk-figure'
      );
      fold.appendChild(
        render_enrichment(message, {
          ...enrichment_handlers,
          show_title: false,
        })
      );
      wrapper.appendChild(fold);
    });
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
    group_turns(model.get('messages') || []).forEach((turn, index) => {
      [
        '',
        '-work',
        '-evidence',
        ...turn.figures.map((_figure, i) => `-enrichr-${i}`),
      ].forEach((suffix) => folds.set(`turn-${index}${suffix}`, open));
    });
  };

  // While Clerk works, the next question can be typed (Ask waits until it's done).
  const IDLE_PLACEHOLDER = textarea.placeholder;
  const setBusy = (busy) => {
    sendBtn.disabled = busy;
    sendBtn.textContent = busy ? '…' : 'Ask';
    textarea.placeholder = busy
      ? 'Clerk is working; type your follow-up and ask when it is done'
      : IDLE_PLACEHOLDER;
  };

  // ---- ask flow ----------------------------------------------------------
  const submit = async () => {
    const question = textarea.value.trim();
    if (!question || model.get('pending')) return;

    setBusy(true);
    textarea.value = '';

    const genes = model.get('gene_list') || [];
    // With an Enrich panel linked, Clerk reads that panel's results instead.
    const { terms: enrichr_terms, short_id } =
      model.get('fetch_enrichr') === false
        ? { terms: [], short_id: '' }
        : await fetchEnrichrTerms(genes);

    requestCounter += 1;
    const id = `${Date.now()}-${requestCounter}`;
    model.set('request', {
      id,
      question,
      gene_list: genes,
      enrichr_terms,
      enrichr_library: ENRICHR_LIB,
      enrichr_short_id: short_id,
    });
    model.save_changes();
  };

  // RETURN: shown once evidence links have changed the views; restores the view
  // the scientist had before following them.
  const back = tool(
    'Return',
    'Return the Landscape and Clustergram to your view before you followed links',
    () => {
      shown_genes = [];
      shown_clusters = [];
      shown_view = '';
      send_now({ restore_view: true });
      mark_shown();
    }
  );
  back.style.color = '#2c7fb8';
  const sync_back = () => {
    back.style.display = model.get('can_restore') ? '' : 'none';
  };
  toolbar.insertBefore(back, toolbar.firstChild);

  // One Expand / Collapse button (and short labels) keep the toolbar on one row
  // in a narrow sidecar, RETURN included.
  const EXPAND_TITLE = 'Open every turn, work log and evidence section';
  let expanded = false;
  const fold_toggle = tool('Expand', EXPAND_TITLE, () => {
    expanded = !expanded;
    set_all_folds(expanded);
    fold_toggle.textContent = expanded ? 'Collapse' : 'Expand';
    fold_toggle.title = expanded
      ? 'Close every turn and section'
      : EXPAND_TITLE;
  });
  tool(
    'Save',
    'Save this conversation to reopen later with OPEN or clerk.load_conversation ' +
      '(reading it needs no Claude; its links need the same data)',
    () => send_request({ save_conversation: true })
  );
  // OPEN reads a saved conversation in the browser and hands it to Python as a
  // one-off message, so it never becomes part of the notebook's widget state.
  const opener = document.createElement('input');
  opener.type = 'file';
  opener.accept = '.json,application/json';
  opener.style.display = 'none';
  opener.addEventListener('change', async () => {
    const file = opener.files?.[0];
    opener.value = '';
    if (!file || model.get('pending')) return;
    model.send?.({
      event: 'load_conversation',
      name: file.name,
      text: await file.text(),
    });
  });
  container.appendChild(opener);
  tool(
    'Open',
    'Open a conversation saved with SAVE (it replaces this one)',
    () => opener.click()
  );
  const reportForm = document.createElement('form');
  reportForm.className = 'clerk-report-form';
  reportForm.hidden = true;
  const reportLabel = document.createElement('label');
  reportLabel.textContent = 'Report name (optional)';
  const reportName = document.createElement('input');
  reportName.type = 'text';
  reportName.name = 'report_title';
  reportName.maxLength = 120;
  reportName.placeholder = 'e.g. Kidney exploration';
  reportLabel.appendChild(reportName);
  const writeReport = document.createElement('button');
  writeReport.type = 'submit';
  writeReport.className = 'clerk-button';
  writeReport.textContent = 'Write report';
  const cancelReport = make_button(
    'Cancel',
    'Close without writing a report',
    () => {
      reportForm.hidden = true;
      textarea.focus();
    }
  );
  cancelReport.type = 'button';
  reportForm.append(reportLabel, writeReport, cancelReport);
  reportForm.addEventListener('submit', (event) => {
    event.preventDefault();
    if (model.get('pending')) return;
    send_request({ export: true, report_title: reportName.value.trim() });
    reportForm.hidden = true;
  });
  container.insertBefore(reportForm, messagesPane);
  tool(
    'Report',
    'Save this conversation as an HTML report with its snapshots, the state to ' +
      'reproduce them, and the recorded cell types (written next to the notebook)',
    () => {
      if (model.get('pending')) return;
      reportForm.hidden = false;
      reportName.focus();
    }
  );

  sendBtn.addEventListener('click', submit);
  textarea.addEventListener('keydown', (e) => {
    // Enter to send, Shift+Enter for newline.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  });

  // ---- briefing ----------------------------------------------------------
  const renderEvidence = () => {
    evidence.replaceChildren();
    // Make it visible when Clerk starts from earlier work (load_briefing).
    const briefing = model.get('briefing_label');
    if (briefing) {
      const line = document.createElement('div');
      line.style.color = '#8a5a00';
      line.style.fontSize = '13px';
      line.style.marginTop = '5px';
      line.title =
        'Clerk receives this earlier work with every question, as conclusions to check';
      line.textContent = briefing;
      evidence.appendChild(line);
    }
  };

  // ---- traitlet listeners ------------------------------------------------
  const onPending = () => {
    renderMessages();
    setBusy(!!model.get('pending'));
  };
  const listeners = [
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
  resize_observer?.observe(container);

  return {
    finalize: () => {
      resize_observer?.disconnect();
      gene_tooltip.destroy();
      listeners.forEach(([event, handler]) => model.off?.(event, handler));
      el.innerHTML = '';
    },
  };
};
