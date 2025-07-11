import { handleAsyncError } from '../temp_utils/errorHandler';

export const refseq_cache = {};

export const fetchRefSeqInfo = async (geneSymbol) => {
  if (geneSymbol in refseq_cache) {
    return refseq_cache[geneSymbol];
  }

  const searchUrl =
    `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=gene&term=${geneSymbol}[sym]&retmode=json`;

  try {
    const searchRes = await fetch(searchUrl);
    const searchJson = await searchRes.json();
    const id = searchJson.esearchresult?.idlist?.[0];
    if (!id) {
      refseq_cache[geneSymbol] = null;
      return null;
    }

    const summaryUrl =
      `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=gene&id=${id}&retmode=json`;
    const summaryRes = await fetch(summaryUrl);
    const summaryJson = await summaryRes.json();
    const doc = summaryJson.result?.[id] || {};
    const info = {
      name: doc.name || '',
      description: doc.summary || '',
      refseq: doc.genomicinfo?.[0]?.chraccver || '',
    };
    refseq_cache[geneSymbol] = info;
    return info;
  } catch (error) {
    handleAsyncError(error, { context: 'fetchRefSeqInfo', url: searchUrl });
    throw error;
  }
};
