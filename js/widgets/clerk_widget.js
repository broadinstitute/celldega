import { postGeneList, fetchEnrichment } from '../external_apis/enrichr_api';
import { handleAsyncError } from '../temp_utils/errorHandler';
import { render_markdown } from '../ui/markdown';

const FONT =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

// Library used to pre-gather Enrichr evidence that rides along in the prompt.
const ENRICHR_LIB = 'CellMarker_2024';
const ENRICHR_TERMS = 8;

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
  sendBtn.textContent = 'Ask';
  sendBtn.style.marginLeft = '5px';
  sendBtn.style.padding = '0 14px';
  sendBtn.style.cursor = 'pointer';
  sendBtn.style.fontFamily = FONT;

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

  container.appendChild(evidence);
  container.appendChild(messagesPane);
  container.appendChild(inputRow);
  el.appendChild(container);

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

    messages.forEach((m) => {
      if (m.role === 'action') {
        // A view change Clerk made (e.g. "Changed the Clustergram: DIM -> 10 ...").
        const note = document.createElement('div');
        note.style.margin = '-4px 0 10px';
        note.style.fontSize = '12px';
        note.style.fontStyle = 'italic';
        note.style.color = '#2c7fb8';
        note.textContent = `↻ ${m.content || ''}`;
        messagesPane.appendChild(note);
        return;
      }
      const row = document.createElement('div');
      row.style.marginBottom = '10px';
      row.style.fontSize = '14px';
      row.style.lineHeight = '1.35';

      const who = document.createElement('div');
      who.style.fontWeight = 'bold';
      who.style.fontSize = '11px';
      who.style.textTransform = 'uppercase';
      who.style.letterSpacing = '0.04em';

      if (m.role === 'user') {
        who.textContent = 'You';
        who.style.color = '#47515b';
      } else if (m.role === 'error') {
        who.textContent = 'Clerk (error)';
        who.style.color = '#c0392b';
        row.style.color = '#c0392b';
      } else {
        who.textContent = 'Clerk';
        who.style.color = '#2c7fb8';
      }

      const body = document.createElement('div');
      if (m.role === 'assistant') {
        // Answers are Markdown; render_markdown escapes all text before adding its
        // own markup, so model output can't inject HTML.
        body.className = 'clerk-md';
        body.innerHTML = render_markdown(m.content || '');
      } else {
        body.style.whiteSpace = 'pre-wrap';
        body.textContent = m.content || '';
      }

      row.appendChild(who);
      row.appendChild(body);
      if (m.role === 'user') renderSentWith(m, row);
      messagesPane.appendChild(row);
    });

    if (pending) {
      const spinner = document.createElement('div');
      spinner.style.color = '#2c7fb8';
      spinner.style.fontSize = '13px';
      spinner.textContent = 'Clerk is thinking…';
      messagesPane.appendChild(spinner);
    }

    messagesPane.scrollTop = messagesPane.scrollHeight;
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
    ['change:messages', renderMessages],
    ['change:pending', onPending],
    ['change:model', modelPicker.sync],
    ['change:effort', effortPicker.sync],
  ];
  listeners.forEach(([event, handler]) => model.on(event, handler));

  modelPicker.sync();
  effortPicker.sync();
  renderEvidence();
  renderMessages();

  return {
    finalize: () => {
      listeners.forEach(([event, handler]) => model.off?.(event, handler));
      el.innerHTML = '';
    },
  };
};
