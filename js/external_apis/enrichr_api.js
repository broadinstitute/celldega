import { handleAsyncError } from '../temp_utils/errorHandler';

export const postGeneList = async (genes) => {
  const url = 'https://amp.pharm.mssm.edu/Enrichr/addList';
  const formData = new FormData();
  formData.append('list', genes.join('\n'));

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });
    const json = await response.json();
    return json.userListId.toString();
  } catch (error) {
    handleAsyncError(error, { context: 'posting gene list to Enrichr', url });
    throw error;
  }
};

export const fetchEnrichment = async (listId, library) => {
  const url = `https://amp.pharm.mssm.edu/Enrichr/enrich?backgroundType=${library}&userListId=${listId}`;
  try {
    const response = await fetch(url);
    return await response.json();
  } catch (error) {
    handleAsyncError(error, { context: 'fetching enrichment', url });
    throw error;
  }
};
