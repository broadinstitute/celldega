/**
 * Shared gene name/description presentation (UniProt-backed).
 *
 * One place defines what a gene "reads like" across the widgets: the hover
 * tooltip lines used by the Clustergram row labels and the Landscape
 * transcript layer, and the scrollable info box shown under a gene search.
 * All of it reads the module-level UniProt cache in `uniprot_api.js`, so a
 * gene fetched in one widget renders instantly in the others.
 */

import {
  get_uniprot_info,
  has_uniprot_info,
  request_uniprot_info,
} from '../external_apis/uniprot_api';

export const escape_html = (value) =>
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const DESCRIPTION_LIMIT = 260;
/** Gene-name blue on light backgrounds (the gene panel, the Enrich tooltip). */
const GENE_INFO_BLUE = '#2f74ff';
/** Lighter pairing for deck.gl's dark tooltip box, where #2f74ff reads muddy. */
const GENE_INFO_BLUE_ON_DARK = '#7fb0ff';

/** True when `axis`'s entities are genes (so UniProt lookups make sense). */
export const is_gene_axis = (viz_state, axis = 'row') => {
  const raw = viz_state?.[`${axis}_entity`];
  const entity = raw?.entity ?? raw;
  return String(entity ?? '').toLowerCase() === 'gene';
};

const truncate = (text, limit = DESCRIPTION_LIMIT) => {
  const value = String(text ?? '').trim();
  if (value.length <= limit) return value;
  return `${value.slice(0, limit).trimEnd()}…`;
};

/**
 * Tooltip lines for a gene: its UniProt full name, then a truncated
 * description. Returns a "Looking up…" placeholder until the fetch lands, and
 * an empty string when UniProt had nothing useful (so the tooltip just shows
 * whatever the caller already rendered).
 *
 * @param {string} gene
 * @returns {string} HTML fragment, already escaped, or '' for no content.
 */
export const gene_info_tooltip_html = (gene) => {
  if (!gene) return '';

  if (!has_uniprot_info(gene)) {
    return '<br><i>Looking up UniProt…</i>';
  }

  const info = get_uniprot_info(gene) || {};
  const name = info.name ? escape_html(info.name) : '';
  // The API module stores this sentinel when a lookup finds nothing.
  const has_description =
    info.description &&
    info.description !== 'Unable to obtain UniProt description.';
  const description = has_description
    ? escape_html(truncate(info.description))
    : '';

  if (!name && !description) return '';

  const name_line = name
    ? `<br><span style="color: ${GENE_INFO_BLUE_ON_DARK};">${name}</span>`
    : '';
  const description_line = description ? `<br>${description}` : '';

  return `${name_line}${description_line}`;
};

/**
 * How long the pointer must rest on a gene before its tooltip (and UniProt
 * lookup) fires. Matches the dwell used by the Enrich bar highlight.
 */
const HOVER_DWELL_MS = 150;

/**
 * Tracks which gene each container is currently showing a tooltip for, so a
 * late-arriving fetch only patches a tooltip the pointer is still on.
 */
const tooltip_gene_by_root = new WeakMap();
/** Pending dwell timer per root, so a fast sweep issues no lookups. */
const tooltip_timer_by_root = new WeakMap();

/**
 * Note the gene under the pointer and, if its UniProt info isn't cached yet,
 * fetch it and re-render the live tooltip when it arrives.
 *
 * deck.gl's `getTooltip` is synchronous, so the first hover renders the
 * "Looking up…" placeholder from {@link gene_info_tooltip_html}; this patches
 * the already-visible `.deck-tooltip` element in place once the data lands
 * (subsequent hovers render straight from cache).
 *
 * @param {HTMLElement} root - Widget root containing `.deck-tooltip`.
 * @param {string|null} gene - Gene under the pointer, or null when leaving.
 * @param {() => string} build_html - Re-builds the full tooltip HTML.
 */
export const refresh_gene_tooltip_async = (root, gene, build_html) => {
  if (!root) return;

  tooltip_gene_by_root.set(root, gene || null);

  // Dwell before hitting the network: deck.gl fires a hover event per pointer
  // move, so dragging down a column of row labels would otherwise queue a
  // lookup for every gene passed over.
  clearTimeout(tooltip_timer_by_root.get(root));
  if (!gene || has_uniprot_info(gene)) return;

  tooltip_timer_by_root.set(
    root,
    setTimeout(() => {
      // Pointer left this gene during the dwell.
      if (tooltip_gene_by_root.get(root) !== gene) return;

      request_uniprot_info(gene)
        .then(() => {
          if (tooltip_gene_by_root.get(root) !== gene) return;

          const tooltip = root.querySelector?.('.deck-tooltip');
          if (!tooltip || tooltip.style.display === 'none') return;

          tooltip.innerHTML = build_html();
        })
        .catch(() => {
          /* handled/logged inside uniprot_get_request */
        });
    }, HOVER_DWELL_MS)
  );
};

/** Firefox reports wheel deltas in lines; approximate a line as 16px. */
const SCROLL_LINE_HEIGHT_PX = 16;

const wheel_delta_px = (event, element) => {
  if (event.deltaMode === 1) return event.deltaY * SCROLL_LINE_HEIGHT_PX;
  if (event.deltaMode === 2) return event.deltaY * (element.clientHeight || 0);
  return event.deltaY;
};

/**
 * The element that actually scrolls for a gesture over `element`: itself if it
 * has overflow, else the nearest ancestor that does. The walk stops before
 * `document.body`, since scrolling the page is exactly what we're preventing.
 */
const nearest_scrollable = (element) => {
  let node = element;

  while (node && node !== document.body && node !== document.documentElement) {
    if (node.scrollHeight > node.clientHeight) return node;
    node = node.parentElement;
  }

  return null;
};

/**
 * Keep wheel gestures over `element` entirely inside it: the page never
 * scrolls (not at the ends of the content, and not when the content doesn't
 * overflow at all), and the widget's own zoom/pan handlers never see the
 * event. Because `preventDefault` also cancels the native scroll, the scroll
 * is re-applied manually to whichever element would have scrolled.
 *
 * Safe to attach to a non-scrolling wrapper: the scroll target is resolved per
 * event, so attaching to inner content still scrolls its overflow container
 * (rather than silently swallowing the gesture).
 *
 * @param {HTMLElement} element
 */
export const contain_scroll = (element) => {
  if (!element) return;

  // Belt and braces for browsers/paths that scroll without a cancelable event.
  element.style.overscrollBehavior = 'contain';

  element.addEventListener(
    'wheel',
    (event) => {
      event.preventDefault();
      event.stopPropagation();

      const target = nearest_scrollable(element);
      if (target) target.scrollTop += wheel_delta_px(event, target);
    },
    { passive: false }
  );
};

/**
 * A floating gene tooltip for plain-DOM widgets (Enrich), where there's no
 * deck.gl `getTooltip` to hook. Deliberately styled like deck.gl's tooltip
 * (its default dark `#29323c` box, with the white text celldega's matrix
 * tooltip sets) so gene hovers look identical across Enrich, the Clustergram,
 * and Landscape.
 *
 * Uses fixed positioning off the pointer's viewport coordinates, so it isn't
 * affected by widget scroll containers or transformed ancestors.
 *
 * Showing is gated behind a short dwell delay, so sweeping the pointer across
 * many genes (or scrolling a list under a stationary pointer) neither flashes
 * tooltips nor fires a UniProt lookup per gene passed over.
 *
 * @param {object} [options]
 * @param {number} [options.delay] - Dwell before showing, in ms.
 * @returns {{show: Function, show_html: Function, move: Function,
 *   hide: Function, destroy: Function}}
 */
export const make_gene_hover_tooltip = (options = {}) => {
  const { delay = HOVER_DWELL_MS } = options;
  const CURSOR_OFFSET_PX = 14;
  const tooltip = document.createElement('div');

  tooltip.className = 'gene_hover_tooltip';
  tooltip.style.position = 'fixed';
  tooltip.style.display = 'none';
  tooltip.style.zIndex = '10000';
  tooltip.style.pointerEvents = 'none';
  tooltip.style.maxWidth = '260px';
  tooltip.style.padding = '10px';
  tooltip.style.background = '#29323c';
  tooltip.style.color = 'white';
  tooltip.style.fontSize = '12px';
  tooltip.style.fontFamily = '"Helvetica Neue", Helvetica, Arial, sans-serif';
  tooltip.style.lineHeight = '1.35';
  document.body.appendChild(tooltip);

  let current_gene = '';
  let dwell_timer = null;

  const render = (gene, extra_html = '') => {
    const info = get_uniprot_info(gene) || {};
    const heading = info.name
      ? `${escape_html(gene)} — ${escape_html(info.name)}`
      : escape_html(gene);
    const body = has_uniprot_info(gene)
      ? escape_html(truncate(info.description))
      : '<i>loading…</i>';

    tooltip.innerHTML = `<span style="color: ${GENE_INFO_BLUE_ON_DARK};">${heading}</span><br>${body}${extra_html}`;
  };

  const place = (point) => {
    tooltip.style.left = `${point.clientX + CURSOR_OFFSET_PX}px`;
    tooltip.style.top = `${point.clientY + CURSOR_OFFSET_PX}px`;
  };

  const cancel_dwell = () => {
    clearTimeout(dwell_timer);
    dwell_timer = null;
  };

  return {
    /**
     * @param {string} gene
     * @param {MouseEvent} event
     * @param {string} [extra_html] - Appended below the description (e.g.
     *   enrichment context for this gene).
     */
    show: (gene, event, extra_html = '') => {
      if (!gene) return;

      cancel_dwell();
      // Coordinates are read now; the event object isn't retained.
      const point = {
        clientX: event?.clientX ?? 0,
        clientY: event?.clientY ?? 0,
      };

      dwell_timer = setTimeout(() => {
        dwell_timer = null;
        current_gene = gene;
        tooltip.style.display = 'block';
        place(point);
        render(gene, extra_html);

        if (!has_uniprot_info(gene)) {
          request_uniprot_info(gene)
            .then(() => {
              // Pointer may have moved on while this was in flight.
              if (current_gene === gene && tooltip.style.display !== 'none') {
                render(gene, extra_html);
              }
            })
            .catch(() => {});
        }
      }, delay);
    },
    /** Show arbitrary content (e.g. enrichment term stats), same dwell. */
    show_html: (html, event) => {
      if (!html) return;

      cancel_dwell();
      const point = {
        clientX: event?.clientX ?? 0,
        clientY: event?.clientY ?? 0,
      };

      dwell_timer = setTimeout(() => {
        dwell_timer = null;
        current_gene = '';
        tooltip.style.display = 'block';
        place(point);
        tooltip.innerHTML = html;
      }, delay);
    },
    move: (event) => {
      if (tooltip.style.display !== 'none') place(event);
    },
    hide: () => {
      cancel_dwell();
      current_gene = '';
      tooltip.style.display = 'none';
    },
    destroy: () => {
      cancel_dwell();
      tooltip.remove();
    },
  };
};

/**
 * A scrollable gene name/description panel (the one Landscape shows under its
 * gene search).
 *
 * This is the *stateful* half of the gene-info UI: it only changes on an
 * explicit selection (row click, search, Enrich gene link), so it stays put
 * as a record of what's selected. Transient hover information belongs in a
 * tooltip ({@link make_gene_hover_tooltip} / the deck.gl tooltips).
 *
 * @param {object} [options]
 * @param {string} [options.width]
 * @param {string} [options.height]
 * @returns {{element: HTMLElement, show: Function, clear: Function}}
 */
export const make_gene_info_box = (options = {}) => {
  const { width = '156px', height = '69px', marginLeft = '0px' } = options;

  const element = document.createElement('div');
  element.className = 'gene_info_box';
  element.textContent = '';
  element.style.marginTop = '3px';
  element.style.marginLeft = marginLeft;
  element.style.color = '#222222';
  element.style.border = '1px solid #d3d3d3';
  element.style.height = height;
  element.style.overflow = 'auto';
  element.style.fontSize = '12px';
  element.style.cursor = 'default';
  element.style.width = width;
  element.style.paddingLeft = '2px';
  element.style.paddingRight = '17px';
  element.style.boxSizing = 'border-box';

  contain_scroll(element);

  let revision = 0;

  const render = async (gene) => {
    const current = ++revision;

    if (!gene) {
      element.innerHTML = '';
      return;
    }

    if (!has_uniprot_info(gene)) {
      element.innerHTML = `<span style="color: ${GENE_INFO_BLUE};">${escape_html(
        gene
      )}</span><br><i>loading…</i>`;
      await request_uniprot_info(gene).catch(() => {});
      // A newer hover/selection landed while this fetch was in flight.
      if (current !== revision) return;
    }

    const info = get_uniprot_info(gene) || {};
    const heading = info.name
      ? `${escape_html(gene)} — ${escape_html(info.name)}`
      : escape_html(gene);
    const description = info.description ? escape_html(info.description) : '';

    element.innerHTML = `<span style="color: ${GENE_INFO_BLUE};">${heading}</span><br>${description}`;
    element.scrollTo?.({ top: 0, behavior: 'smooth' });
  };

  return {
    element,
    /** Show `gene` — call only from an explicit selection, not from hover. */
    show: (gene) => render(gene || ''),
    clear: () => render(''),
  };
};
