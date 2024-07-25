
export let uniprot_data = {}

export const uniprot_get_request = async (gene_symbol) => {

    console.log('gene_symbol', gene_symbol)

    // Uniprot fetch
    /////////////////////////////////////////////

    // get Uniprot Accession Number
    ///////////////////////////////////
    let organism = 'human';
    let num_matches = 100;
    let url_accession = `https://www.ebi.ac.uk/proteins/api/proteins?offset=0&size=${num_matches}&exact_gene=${gene_symbol}&organism=${organism}`;



    // try {

        console.log('trying fetch request')

        // const response = await fetch(url_accession);

        const response = await fetch(url_accession, {
            headers: {
              'Accept': 'application/json'
            }
          });

        const data = await response.json(); // get response as JSON

        console.log(data)

        // console.log(response)

        // const text = await response.text(); // get response as text

        // // // Log the response text for debugging
        // // console.log('text', text);

        // // Parse XML response
        // let parser = new DOMParser();
        // let xmlDoc = parser.parseFromString(text, "application/xml");

        // let entries = xmlDoc.getElementsByTagName("entry");

        // console.log('entries')

        // console.log(entries)

        // let real_protein = Array.from(entries)
        //     // has gene
        //     .filter(entry => entry.getElementsByTagName("gene").length > 0)
        //     // matches gene name in first entry (lowercase string)
        //     .filter(entry => entry.getElementsByTagName("gene")[0].getElementsByTagName("name")[0].textContent.toLowerCase() === gene_symbol.toLowerCase())
        //     // has evidence at protein level (assuming this is a custom attribute you need to check)
        //     .filter(entry => {
        //         let proteinExistence = entry.getElementsByTagName("proteinExistence")[0];
        //         return proteinExistence && proteinExistence.textContent === 'Evidence at protein level';
        //     });

        // console.log(real_protein)

        // const data = await response.json();

        // console.log(data)

        // let real_protein = data
        //     // has evidence at protein level
        //     .filter(d => d.proteinExistence === 'Evidence at protein level')
        //     // has a comments section
        //     .filter(d => 'comments' in d)
        //     // has gene
        //     .filter(d => 'gene' in d)
        //     // matches gene name in first entry (lowercase string)
        //     .filter(d => d.gene[0].name.value.toLowerCase() === gene_symbol.toLowerCase())
        //     // has a rank by the number of comments
        //     .sort((a, b) => b.comments.length - a.comments.length);

        // console.log('real_protein', real_protein)

        // if (real_protein.length > 0) {
        //     let inst_accession = real_protein[0].accession;
        //     let base_url_info = `https://rest.uniprot.org/uniprotkb/${inst_accession}.json`;

        //     try {
        //         const response_info = await fetch(base_url_info);
        //         const data_info = await response_info.json();

        //         try {
        //             let full_name = data_info.proteinDescription.recommendedName.fullName.value;
        //             let description = data_info.comments?.[0]?.texts?.[0]?.value || 'Unable to obtain UniProt description.';

        //             // // handle success
        //             // set_tooltip(ini_gene_symbol, full_name, description);

        //             // save data for repeated use
        //             uniprot_data[gene_symbol] = {
        //                 name: full_name,
        //                 description: description
        //             };

        //         } catch(error) {
        //             uniprot_data[gene_symbol] = {
        //                 name: '',
        //                 description: 'Unable to obtain UniProt description.'
        //             };
        //             // set_tooltip(ini_gene_symbol, '', 'Unable to obtain UniProt description.');
        //         }

        //     } catch (error){
        //         uniprot_data[gene_symbol] = {
        //             name: '',
        //             description: 'Unable to obtain UniProt description.'
        //         };
        //         // set_tooltip(ini_gene_symbol, '', 'Unable to obtain UniProt description.');
        //     }

        // }





    // } catch (error) {

    //     console.log('fetch request did not work')

    //     uniprot_data[gene_symbol] = {
    //         name: '',
    //         description: 'Unable to obtain UniProt description.'
    //     };
    //     // set_tooltip(ini_gene_symbol, '', 'Unable to obtain UniProt description.');
    // }

}

// function set_tooltip(gene_symbol, full_name, description){

// if (full_name != undefined){

//     // assign html
//     d3.select(params.tooltip_id)
//     .html(function(){
//         var sym_name = gene_symbol + ': ' + full_name;
//         var full_html = '<p>' + sym_name + '</p> <p>' +
//             description + '</p>';
//         return full_html;
//     });

//     //set width
//     d3.select(params.tooltip_id)
//     .selectAll('p')
//     .style('width', '600px');
// }
// }

// function gene_info(gene_symbol){

// if (_.has(uniprot_data, gene_symbol)){
//     var inst_data = uniprot_data[gene_symbol];
//     set_tooltip(gene_symbol, inst_data.name, inst_data.description);
// } else{
//     get_request(gene_symbol);
// }

// }

//   var hzome = {}

//   hzome.gene_info = gene_info;
//   hzome.gene_data = params.gene_data;
//   hzome.get_request = get_request;

//   return hzome;


