/**
 * How the Clerk panel organizes a conversation: one collapsible turn per question,
 * the intermediate work (lookups, view changes, interim replies) folded away, and the
 * final answer up front with its "Evidence:" bullets collapsed.
 */

/**
 * Group chat messages into turns, one per question.
 *
 * Within a turn, the last Clerk reply is the answer (once Clerk has finished); earlier
 * replies and the lookups / changes before the answer are its work. Lines after the
 * answer (cell types recorded, a view change shown with it) are its results.
 *
 * @param {object[]} messages - {role: 'user'|'assistant'|'action'|'error'|'pause', ...}
 * @param {boolean} pending - Clerk is still working on the last question.
 * @returns {{question: object|null, work: object[], answer: object|null,
 *   results: object[], errors: object[], pause: object|null, pending: boolean}[]}
 */
export const group_turns = (messages = [], pending = false) => {
  const turns = [];
  let current = null;
  const start = (question) => {
    current = { question, items: [] };
    turns.push(current);
  };
  messages.forEach((message) => {
    if (message?.role === 'user') start(message);
    else {
      if (!current) start(null);
      current.items.push(message);
    }
  });

  return turns.map(({ question, items }, index) => {
    const is_pending = pending && index === turns.length - 1;
    const answer_at = is_pending
      ? -1
      : items.map((m) => m?.role).lastIndexOf('assistant');
    const turn = {
      question,
      work: [],
      answer: answer_at >= 0 ? items[answer_at] : null,
      results: [],
      // Enrichr results drawn like the Enrich panel, in view rather than in Work.
      figures: [],
      errors: [],
      pause: null,
      pending: is_pending,
    };
    items.forEach((message, i) => {
      const role = message?.role;
      if (role === 'enrichment') turn.figures.push(message);
      else if (role === 'error') turn.errors.push(message);
      else if (role === 'pause') turn.pause = message;
      else if (i === answer_at) {
        // the answer itself
      } else if (answer_at >= 0 && i > answer_at) turn.results.push(message);
      else turn.work.push(message);
    });
    // A pause is only actionable while it is the latest thing in the conversation.
    if (turn.pause && items[items.length - 1] !== turn.pause) turn.pause = null;
    return turn;
  });
};

// "Evidence:", "**Evidence:**", "**Evidence**:" or a "## Evidence" heading; not
// prose such as "Evidence suggests...".
const EVIDENCE_LINE =
  /^\s*(?:#{1,6}\s*)?(?:\*\*|__)?evidence(?:\*\*|__)?\s*(?::\s*(?:\*\*|__)?|(?:\*\*|__)?\s*$)\s*(.*)$/i;
const LIST_ITEM = /^\s*(?:[-*+]|\d+[.)])\s+/;

/**
 * Split an answer into the short answer and its "Evidence:" section.
 *
 * A closing line after the evidence bullets (typically the yes/no next step) is kept
 * visible, after the collapsed evidence.
 *
 * @param {string} text
 * @returns {{main: string, evidence: string|null, after: string}}
 */
export const split_evidence = (text = '') => {
  const lines = String(text).split('\n');
  const at = lines.findIndex((line) => EVIDENCE_LINE.test(line));
  if (at < 0) return { main: String(text), evidence: null, after: '' };
  const first = lines[at].match(EVIDENCE_LINE)[1].trim();
  const rest = lines.slice(at + 1);
  // Everything after the last list item (and its continuation lines) stays visible.
  let last_item = -1;
  rest.forEach((line, i) => {
    if (LIST_ITEM.test(line)) last_item = i;
  });
  let end = rest.length;
  if (last_item >= 0) {
    end = last_item + 1;
    while (end < rest.length && /^\s+\S/.test(rest[end])) end += 1;
  }
  const evidence = [first, ...rest.slice(0, end)].join('\n').trim();
  if (!evidence) return { main: String(text), evidence: null, after: '' };
  return {
    main: lines.slice(0, at).join('\n').trim(),
    evidence,
    after: rest.slice(end).join('\n').trim(),
  };
};

/**
 * Whether a reply ends by asking the scientist something (a Yes button is offered).
 * @param {string} text
 */
export const asks_question = (text = '') => {
  const lines = String(text)
    .trim()
    .split('\n')
    .filter((line) => line.trim());
  if (!lines.length) return false;
  const last = lines[lines.length - 1].replace(/[\s*_)`"'”’]+$/, '');
  return last.endsWith('?');
};

const TOKEN = /[A-Za-z0-9][A-Za-z0-9._-]*/g;

/**
 * Turn known gene names in rendered text into clickable links (in place).
 *
 * Matches like Python's Clerk._find_names: exactly, or case-insensitively when the
 * word is written in capitals or contains a digit, so ordinary words aren't linked.
 * Text inside links and code blocks is left alone.
 *
 * @param {HTMLElement} root - Rendered Markdown.
 * @param {string[]} genes - Gene names to link (canonical spelling).
 * @param {(gene: string, add: boolean) => void} on_click - `add` is true for
 *   shift-click.
 * @param {{show?: Function, move?: Function, hide?: Function}} [hover] - Hover
 *   handlers, e.g. the shared UniProt gene tooltip (make_gene_hover_tooltip).
 * @returns {number} How many links were made.
 */
export const link_genes = (
  root,
  genes = [],
  on_click = () => {},
  hover = {}
) => {
  if (!genes.length) return 0;
  const exact = new Set(genes);
  const by_upper = new Map();
  genes.forEach((gene) => {
    const upper = gene.toUpperCase();
    if (!by_upper.has(upper)) by_upper.set(upper, gene);
  });
  const resolve = (raw) => {
    // Dots and dashes occur inside symbols (HLA-DRA), not at their end.
    const token = raw.replace(/[._-]+$/, '');
    if (exact.has(token)) return [token, token.length];
    if (token === token.toUpperCase() || /\d/.test(token)) {
      const name = by_upper.get(token.toUpperCase());
      if (name) return [name, token.length];
    }
    return null;
  };

  const doc = root.ownerDocument;
  const walker = doc.createTreeWalker(root, 4 /* NodeFilter.SHOW_TEXT */, {
    acceptNode: (node) =>
      node.parentElement?.closest('a, pre, .clerk-gene') ? 2 : 1, // reject : accept
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);

  let linked = 0;
  nodes.forEach((node) => {
    const text = node.nodeValue;
    const fragment = doc.createDocumentFragment();
    let last = 0;
    [...text.matchAll(TOKEN)].forEach((match) => {
      const hit = resolve(match[0]);
      if (!hit) return;
      const [name, length] = hit;
      fragment.append(text.slice(last, match.index));
      const link = doc.createElement('span');
      link.className = 'clerk-gene';
      link.dataset.gene = name;
      link.textContent = text.slice(match.index, match.index + length);
      link.tabIndex = 0;
      link.setAttribute('role', 'button');
      link.setAttribute(
        'aria-label',
        `${name}: show on the Landscape and Clustergram (shift-click adds it)`
      );
      link.addEventListener('click', (event) => {
        hover.hide?.();
        on_click(name, event.shiftKey);
      });
      link.addEventListener('mouseenter', (event) => hover.show?.(name, event));
      link.addEventListener('mousemove', (event) => hover.move?.(event));
      link.addEventListener('mouseleave', () => hover.hide?.());
      link.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          on_click(name, event.shiftKey);
        }
      });
      fragment.append(link);
      last = match.index + length;
      linked += 1;
    });
    if (last > 0) {
      fragment.append(text.slice(last));
      node.replaceWith(fragment);
    }
  });
  return linked;
};

// "cluster 4", "clusters 4, 5 and 12", "clusters 4/5".
const CLUSTER_PHRASE =
  /\b(clusters?)(\s+)([A-Za-z0-9_+-]+(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+|\s*&\s*|\s*\/\s*)[A-Za-z0-9_+-]+)*)/gi;
const CLUSTER_ID = /[A-Za-z0-9_+-]+/g;

/**
 * Turn cluster references ("cluster 4", "clusters 4, 5 and 12") into links, for the
 * cluster names given. Text inside links and code blocks is left alone.
 *
 * @param {HTMLElement} root
 * @param {string[]} clusters - Known cluster names.
 * @param {(cluster: string, add: boolean) => void} on_click
 * @param {{show?: Function, move?: Function, hide?: Function}} [hover] - `show` gets
 *   (cluster, event).
 * @returns {number} How many links were made.
 */
export const link_clusters = (
  root,
  clusters = [],
  on_click = () => {},
  hover = {}
) => {
  if (!clusters.length) return 0;
  const known = new Set(clusters.map(String));
  const doc = root.ownerDocument;
  const walker = doc.createTreeWalker(root, 4 /* NodeFilter.SHOW_TEXT */, {
    acceptNode: (node) =>
      node.parentElement?.closest('a, pre, .clerk-gene, .clerk-cluster')
        ? 2
        : 1,
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);

  let linked = 0;
  nodes.forEach((node) => {
    const text = node.nodeValue;
    const fragment = doc.createDocumentFragment();
    let last = 0;
    [...text.matchAll(CLUSTER_PHRASE)].forEach((phrase) => {
      const ids_start = phrase.index + phrase[1].length + phrase[2].length;
      [...phrase[3].matchAll(CLUSTER_ID)].forEach((id_match) => {
        const id = id_match[0];
        if (!known.has(id)) return;
        const start = ids_start + id_match.index;
        fragment.append(text.slice(last, start));
        const link = doc.createElement('span');
        link.className = 'clerk-cluster';
        link.dataset.cluster = id;
        link.textContent = id;
        link.tabIndex = 0;
        link.setAttribute('role', 'button');
        link.setAttribute(
          'aria-label',
          `cluster ${id}: highlight in the Landscape (shift-click adds it)`
        );
        link.addEventListener('click', (event) => {
          hover.hide?.();
          on_click(id, event.shiftKey);
        });
        link.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            on_click(id, event.shiftKey);
          }
        });
        link.addEventListener('mouseenter', (event) => hover.show?.(id, event));
        link.addEventListener('mousemove', (event) => hover.move?.(event));
        link.addEventListener('mouseleave', () => hover.hide?.());
        fragment.append(link);
        last = start + id.length;
        linked += 1;
      });
    });
    if (last > 0) {
      fragment.append(text.slice(last));
      node.replaceWith(fragment);
    }
  });
  return linked;
};
