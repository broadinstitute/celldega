import * as d3 from 'd3';

import {
  uniprot_data,
  uniprot_get_request,
} from '../external_apis/uniprot_api';
import { handleAsyncError } from '../temp_utils/errorHandler';

export const updateParagraphColors = (element, term_genes) => {
  const common = term_genes || [];
  d3.select(element)
    .selectAll('span')
    .style('color', (d) => {
      const inst_gene = d.toLowerCase().replace(', ', '');
      if (common.length > 0) {
        return common.includes(inst_gene) ? 'blue' : '#2F4F4F';
      }
      return 'black';
    });
};

export const updateGeneInfo = async (gene, geneInfoHolder) => {
  if (!gene) {
    geneInfoHolder.textContent = '';
    return;
  }
  try {
    await uniprot_get_request(gene);
    const info = uniprot_data[gene] || { name: '', description: '' };
    const boldElement = document.createElement('b');
    boldElement.textContent = `${gene}: ${info.name}`;
    boldElement.style.fontFamily = 'inherit';
    boldElement.style.fontSize = '12px';
    boldElement.style.lineHeight = '1.35';
    const paragraphElement = document.createElement('p');
    paragraphElement.textContent = info.description;
    paragraphElement.style.fontFamily = 'inherit';
    paragraphElement.style.fontSize = '12px';
    paragraphElement.style.lineHeight = '1.35';
    paragraphElement.style.margin = '4px 0 0';
    geneInfoHolder.textContent = ''; // Clear existing content
    geneInfoHolder.appendChild(boldElement);
    geneInfoHolder.appendChild(paragraphElement);
  } catch (error) {
    handleAsyncError(error, { context: 'updateGeneInfo' });
  }
};
