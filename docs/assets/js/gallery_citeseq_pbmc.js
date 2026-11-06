import celldega from './celldega.js';

document.addEventListener('DOMContentLoaded', async () => {
  const element = document.getElementById('clustergram-citeseq-pbmc');
  if (!element) return;

  // A clustered Matrix written with Matrix.write_zarr, pinned to a dataset commit.
  const url =
    'https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/' +
    'resolve/37c10145fc0c9d4237438a754a334e044540ae06/' +
    'Flex_16k_PBMC_CITE-seq/matrices/cell_types.zarr';

  try {
    await celldega.matrix_from_zarr(element, { url, width: 800, height: 700 });
  } catch (error) {
    element.textContent =
      'The Clustergram could not load. Please reload to try again.';
    console.error('Unable to load the CITE-seq gallery Clustergram', error);
  }
});
