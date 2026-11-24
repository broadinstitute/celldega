import { handleAsyncError } from '../temp_utils/errorHandler';
import { base_display_label } from '../utils/display_label';

/**
 * Gene symbol -> `{ name, description }`. Module-level, so every widget in the
 * bundle (Landscape, Clustergram, Yearbook, Enrich) shares one cache: a gene
 * looked up in one widget is instant in the others.
 */
export const uniprot_data = {};

/** In-flight requests, so concurrent hovers on one gene issue a single fetch. */
const uniprot_pending = new Map();

const is_mock_gene = (gene_symbol) => /^MockGene\d+$/i.test(gene_symbol);

/**
 * Longest a lookup (both requests) may take. A request that hangs, e.g. behind
 * a firewall that drops packets, would otherwise never settle, and transcript
 * tooltips wait for the lookup before appearing.
 */
export const UNIPROT_TIMEOUT_MS = 5000;

/**
 * A lookup that failed (a service outage, a timeout) is tried again on a hover
 * after this long, so a gene doesn't keep "Unable to obtain..." all session. A
 * gene UniProt has nothing for is cached for good.
 */
export const UNIPROT_RETRY_MS = 60000;

const FALLBACK_DESCRIPTION = 'Unable to obtain UniProt description.';

/** When each failed lookup was cached (see UNIPROT_RETRY_MS). */
const uniprot_failed_at = new Map();

const is_timeout = (error) => error?.name === 'AbortError';

/** A service answered with an error (e.g. HTTP 500 during an outage). */
class ServiceError extends Error {}

const fetch_json = async (url, signal) => {
  const response = await fetch(url, {
    headers: { Accept: 'application/json' },
    signal,
  });
  if (!response.ok) throw new ServiceError(`HTTP ${response.status}`);
  return response.json();
};

/**
 * Strip Celldega's display-only multi-omic modality suffix before lookup.
 *
 * Feature-stacked matrices use IDs such as ``CDH1::rna`` so same-named
 * measurements remain distinct. UniProt expects the base symbol, while the
 * full ID remains the visual label and cache key. Single colons are left alone
 * because metabolite names can legitimately contain them (for example,
 * ``C38:5 PC``).
 */
export const uniprot_query_symbol = base_display_label;

const same_gene = (name, query_symbol) =>
  String(name || '').toLowerCase() === query_symbol.toLowerCase();

/**
 * The EBI Proteins API's best-documented human protein for the gene, then its
 * UniProt entry. Returns null when there is none.
 */
const ebi_lookup = async (query_symbol, signal) => {
  const url = `https://www.ebi.ac.uk/proteins/api/proteins?offset=0&size=100&exact_gene=${encodeURIComponent(query_symbol)}&organism=human`;
  const data = await fetch_json(url, signal);
  if (!Array.isArray(data)) throw new ServiceError('unexpected response');
  const real_protein = data
    .filter((d) => d.proteinExistence === 'Evidence at protein level')
    .filter((d) => 'comments' in d)
    .filter((d) => 'gene' in d)
    .filter((d) => same_gene(d.gene[0]?.name?.value, query_symbol))
    .sort((a, b) => b.comments.length - a.comments.length);
  if (!real_protein.length) return null;
  const info = await fetch_json(
    `https://rest.uniprot.org/uniprotkb/${real_protein[0].accession}.json`,
    signal
  );
  return {
    name: info.proteinDescription?.recommendedName?.fullName?.value || '',
    description: info.comments?.[0]?.texts?.[0]?.value || FALLBACK_DESCRIPTION,
  };
};

/** UniProt's own search (reviewed human entries), one request: the fallback. */
const uniprot_search = async (query_symbol, signal) => {
  const query = `gene_exact:${query_symbol} AND organism_id:9606 AND reviewed:true`;
  const url = `https://rest.uniprot.org/uniprotkb/search?query=${encodeURIComponent(query)}&fields=accession,gene_primary,protein_name,cc_function&format=json&size=5`;
  const data = await fetch_json(url, signal);
  const entry = (data?.results || []).find((result) =>
    same_gene(result.genes?.[0]?.geneName?.value, query_symbol)
  );
  if (!entry) return null;
  return {
    name: entry.proteinDescription?.recommendedName?.fullName?.value || '',
    description:
      entry.comments?.find((c) => c.commentType === 'FUNCTION')?.texts?.[0]
        ?.value || FALLBACK_DESCRIPTION,
  };
};

/** Cached, and not a failure that's due a retry. */
const is_cached = (gene_symbol) => {
  if (!(gene_symbol in uniprot_data)) return false;
  const failed_at = uniprot_failed_at.get(gene_symbol);
  return failed_at === undefined || Date.now() - failed_at < UNIPROT_RETRY_MS;
};

export const uniprot_get_request = async (gene_symbol) => {
  const query_symbol = uniprot_query_symbol(gene_symbol);
  if (!query_symbol) return;

  if (is_mock_gene(query_symbol)) {
    uniprot_data[gene_symbol] = {
      name: '',
      description: '',
    };
    return;
  }

  if (is_cached(gene_symbol)) return;

  // A lookup (both services) gives up after UNIPROT_TIMEOUT_MS.
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), UNIPROT_TIMEOUT_MS);
  const { signal } = controller;
  let gene_data = null;
  let failed = false;
  try {
    gene_data = await ebi_lookup(query_symbol, signal);
  } catch (error) {
    if (is_timeout(error)) {
      failed = true; // offline or blocked: don't wait on a second service
    } else {
      // Logged unless the service just answered with an error (an outage).
      if (!(error instanceof ServiceError)) {
        handleAsyncError(error, {
          context: `searching for gene ${query_symbol}`,
          logUnexpected: true,
          throwOnAuth: false,
        });
      }
      try {
        gene_data = await uniprot_search(query_symbol, signal);
      } catch {
        failed = true;
      }
    }
  } finally {
    clearTimeout(timeout);
  }

  uniprot_data[gene_symbol] = gene_data || {
    name: '',
    description: FALLBACK_DESCRIPTION,
  };
  if (failed) uniprot_failed_at.set(gene_symbol, Date.now());
  else uniprot_failed_at.delete(gene_symbol);
};

/** Cached info for `gene_symbol`, or `undefined` if it hasn't been fetched. */
export const get_uniprot_info = (gene_symbol) =>
  gene_symbol ? uniprot_data[gene_symbol] : undefined;

/** Whether `gene_symbol` has cached info (a failed lookup due a retry doesn't). */
export const has_uniprot_info = (gene_symbol) =>
  Boolean(gene_symbol) && is_cached(gene_symbol);

/**
 * Cache-first fetch that collapses concurrent requests for the same gene into
 * one network call. Prefer this over calling {@link uniprot_get_request}
 * directly from hover paths, which can fire many times per second.
 *
 * @param {string} gene_symbol
 * @returns {Promise<{name: string, description: string}|undefined>}
 */
export const request_uniprot_info = (gene_symbol) => {
  if (!gene_symbol) return Promise.resolve(undefined);
  if (is_cached(gene_symbol)) {
    return Promise.resolve(uniprot_data[gene_symbol]);
  }

  let pending = uniprot_pending.get(gene_symbol);
  if (!pending) {
    pending = uniprot_get_request(gene_symbol)
      .then(() => uniprot_data[gene_symbol])
      .finally(() => uniprot_pending.delete(gene_symbol));
    uniprot_pending.set(gene_symbol, pending);
  }

  return pending;
};
