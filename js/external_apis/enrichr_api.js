import { handleAsyncError } from '../temp_utils/errorHandler';

export const postGeneList = async (genes, background = null) => {
  const url = 'https://maayanlab.cloud/Enrichr/addList';
  const formData = new FormData();
  formData.append('list', genes.join('\n'));
  if (background && Array.isArray(background) && background.length > 0) {
    formData.append('background', background.join('\n'));
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });
    const json = await response.json();
    return {
      userListId: json.userListId.toString(),
      shortId: json.shortId || null,
    };
  } catch (error) {
    handleAsyncError(error, { context: 'posting gene list to Enrichr', url });
    throw error;
  }
};

export const fetchEnrichment = async (listId, library) => {
  const url = `https://maayanlab.cloud/Enrichr/enrich?backgroundType=${library}&userListId=${listId}`;
  try {
    const response = await fetch(url);
    return await response.json();
  } catch (error) {
    handleAsyncError(error, { context: 'fetching enrichment', url });
    throw error;
  }
};
