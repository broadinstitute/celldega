import { handleAsyncError } from '../temp_utils/errorHandler';

export const uniprot_data = {};

export const uniprot_get_request = async (gene_symbol) => {
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
