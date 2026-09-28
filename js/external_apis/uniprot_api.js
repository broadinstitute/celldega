import { handleAsyncError } from '../temp_utils/errorHandler';

/**
 * Gene symbol -> `{ name, description }`. Module-level, so every widget in the
 * bundle (Landscape, Clustergram, Yearbook, Enrich) shares one cache: a gene
 * looked up in one widget is instant in the others.
 */
export const uniprot_data = {};

/** In-flight requests, so concurrent hovers on one gene issue a single fetch. */
const uniprot_pending = new Map();

const is_mock_gene = (gene_symbol) => /^MockGene\d+$/i.test(gene_symbol);

export const uniprot_get_request = async (gene_symbol) => {
  if (is_mock_gene(gene_symbol)) {
    uniprot_data[gene_symbol] = {
      name: '',
      description: '',
    };
    return;
  }

  if (!(gene_symbol in uniprot_data)) {
    let gene_data = {
      name: '',
      description: 'Unable to obtain UniProt description.',
    };

    const organism = 'human';
    const num_matches = 100;
    const url_accession = `https://www.ebi.ac.uk/proteins/api/proteins?offset=0&size=${num_matches}&exact_gene=${gene_symbol}&organism=${organism}`;

    try {
      const response = await fetch(url_accession, {
        headers: {
          Accept: 'application/json',
        },
      });

      const data = await response.json();

      const real_protein = data
        .filter((d) => d.proteinExistence === 'Evidence at protein level')
        .filter((d) => 'comments' in d)
        .filter((d) => 'gene' in d)
        .filter(
          (d) =>
            d.gene[0].name.value.toLowerCase() === gene_symbol.toLowerCase()
        )
        .sort((a, b) => b.comments.length - a.comments.length);

      if (real_protein.length > 0) {
        const inst_accession = real_protein[0].accession;
        const base_url_info = `https://rest.uniprot.org/uniprotkb/${inst_accession}.json`;

        try {
          const response_info = await fetch(base_url_info);
          const data_info = await response_info.json();

          const full_name =
            data_info.proteinDescription?.recommendedName?.fullName?.value ||
            '';
          const description =
            data_info.comments?.[0]?.texts?.[0]?.value ||
            'Unable to obtain UniProt description.';

          gene_data = {
            name: full_name,
            description,
          };
        } catch (error) {
          handleAsyncError(error, {
            context: `fetching detailed info for ${gene_symbol}`,
            url: base_url_info,
            logUnexpected: true,
            throwOnAuth: false,
          });
        }
      }
    } catch (error) {
      handleAsyncError(error, {
        context: `searching for gene ${gene_symbol}`,
        url: url_accession,
        logUnexpected: true,
        throwOnAuth: false,
      });
    }

    uniprot_data[gene_symbol] = gene_data;
  }
};

/** Cached info for `gene_symbol`, or `undefined` if it hasn't been fetched. */
export const get_uniprot_info = (gene_symbol) =>
  gene_symbol ? uniprot_data[gene_symbol] : undefined;

export const has_uniprot_info = (gene_symbol) =>
  Boolean(gene_symbol) && gene_symbol in uniprot_data;

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
  if (gene_symbol in uniprot_data) {
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
