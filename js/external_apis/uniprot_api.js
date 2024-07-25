
export let uniprot_data = {}

export const uniprot_get_request = async (gene_symbol) => {

    if (!(gene_symbol in uniprot_data)) {

        let gene_data

        let organism = 'human';
        let num_matches = 100;
        let url_accession = `https://www.ebi.ac.uk/proteins/api/proteins?offset=0&size=${num_matches}&exact_gene=${gene_symbol}&organism=${organism}`;

        try {

            const response = await fetch(url_accession, {
                headers: {
                'Accept': 'application/json'
                }
            });

            const data = await response.json(); // get response as JSON

            let real_protein = data
                // has evidence at protein level
                .filter(d => d.proteinExistence === 'Evidence at protein level')
                // has a comments section
                .filter(d => 'comments' in d)
                // has gene
                .filter(d => 'gene' in d)
                // matches gene name in first entry (lowercase string)
                .filter(d => d.gene[0].name.value.toLowerCase() === gene_symbol.toLowerCase())
                // has a rank by the number of comments
                .sort((a, b) => b.comments.length - a.comments.length);

            if (real_protein.length > 0) {
                let inst_accession = real_protein[0].accession;
                let base_url_info = `https://rest.uniprot.org/uniprotkb/${inst_accession}.json`;

                try {
                    const response_info = await fetch(base_url_info);
                    const data_info = await response_info.json();

                    try {
                        let full_name = data_info.proteinDescription.recommendedName.fullName.value;
                        let description = data_info.comments?.[0]?.texts?.[0]?.value || 'Unable to obtain UniProt description.';

                        gene_data = {
                            name: full_name,
                            description: description
                        };

                    } catch(error) {
                        gene_data = {
                            name: '',
                            description: 'Unable to obtain UniProt description.'
                        }

                    }

                } catch (error){
                    gene_data = {
                        name: '',
                        description: 'Unable to obtain UniProt description.'
                    }

                }

            }

        } catch (error) {

            gene_data = {
                name: '',
                description: 'Unable to obtain UniProt description.'
            }

        }

        uniprot_data[gene_symbol] = gene_data
    }

}

