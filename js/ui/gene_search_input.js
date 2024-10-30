export const set_gene_search_input = (genes) => {

    let gene_search_input = document.createElement("input");
    gene_search_input.setAttribute('type', 'text');
    gene_search_input.setAttribute('placeholder', 'Gene search');
    gene_search_input.style.width = "500px";
    gene_search_input.style.height = "20px";
    gene_search_input.style.marginTop = "5px";
    gene_search_input.style.display = "inline-block";
    gene_search_input.style.padding = "1pt 2pt";

    genes.gene_search_input = gene_search_input
}