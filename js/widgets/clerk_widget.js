import { postGeneList, fetchEnrichment } from '../external_apis/enrichr_api';
import { handleAsyncError } from '../temp_utils/errorHandler';

const FONT =
  '-apple-system, BlinkMacSystemFont, "San Francisco", "Helvetica Neue", Helvetica, Arial, sans-serif';

// Library used to pre-gather Enrichr evidence that rides along in the prompt.
const ENRICHR_LIB = 'CellMarker_2024';
const ENRICHR_TERMS = 8;

/**
 * Celldega Clerk chat UI. Mirrors the Enrich widget's plumbing, but instead of
 * rendering enrichment bars it collects a free-form question, pre-gathers evidence
 * (gene list + Enrichr terms), and hands it to the Python side (which calls Claude).
 */
export const render_clerk = async ({ model, el }) => {
  const width = (model.get('width') || 650) - 5;
  const height = model.get('height') || 650;

  const enrichrCache = {};
  let requestCounter = 0;

  // ---- layout ------------------------------------------------------------
  const container = document.createElement('div');
  container.style.width = `${width}px`;
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
  evidence.style.maxHeight = '150px';
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
    'Ask Clerk about this cluster (e.g. "What cell type is this?")';
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

  inputRow.appendChild(textarea);
  inputRow.appendChild(sendBtn);

  container.appendChild(evidence);
  container.appendChild(messagesPane);
  container.appendChild(inputRow);
  el.appendChild(container);

  // ---- rendering helpers -------------------------------------------------
  const renderEvidence = () => {
    const genes = model.get('gene_list') || [];
    const image = model.get('image_b64') || '';
    evidence.innerHTML = '';

    const title = document.createElement('div');
    title.textContent = 'Evidence';
    title.style.fontWeight = 'bold';
    title.style.fontSize = '12px';
    title.style.color = '#47515b';
    evidence.appendChild(title);

    const geneLine = document.createElement('div');
    geneLine.style.fontSize = '13px';
    geneLine.style.marginTop = '3px';
    geneLine.textContent = genes.length
      ? `Genes (${genes.length}): ${genes.join(', ')}`
      : 'No gene list provided.';
    evidence.appendChild(geneLine);

    if (image) {
      const img = document.createElement('img');
      img.src = `data:image/png;base64,${image}`;
      img.style.maxWidth = '100%';
      img.style.maxHeight = '90px';
      img.style.marginTop = '4px';
      img.style.border = '1px solid #d3d3d3';
      img.title = 'Landscape raster attached to the prompt';
      evidence.appendChild(img);
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
      const row = document.createElement('div');
      row.style.marginBottom = '10px';
      row.style.fontSize = '14px';
      row.style.whiteSpace = 'pre-wrap';
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
      body.textContent = m.content || '';

      row.appendChild(who);
      row.appendChild(body);
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
    const enrichr_terms = await fetchEnrichrTerms(genes);

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
  model.on('change:gene_list', renderEvidence);
  model.on('change:image_b64', renderEvidence);
  model.on('change:messages', renderMessages);
  model.on('change:pending', () => {
    renderMessages();
    setBusy(!!model.get('pending'));
  });

  renderEvidence();
  renderMessages();

  return {
    finalize: () => {
      el.innerHTML = '';
    },
  };
};
