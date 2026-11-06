import celldega from './celldega.js';

document.addEventListener('DOMContentLoaded', async () => {
  const element = document.getElementById('landscape-atera-kidney');
  if (!element) return;

  const baseUrl =
    'https://raw.githubusercontent.com/broadinstitute/' +
    'Celldega_Atera_v1_WTA_Kidney_non_diseased_FFPE/' +
    '3a46ab4db67821eef3b8ff8d1c3704fb7b3bb48f';

  try {
    await celldega.landscape_ist(
      element,
      {},
      '',
      28322,
      16570,
      0,
      -6.5,
      baseUrl,
      '',
      0.25,
      0,
      800
    );
  } catch (error) {
    element.textContent =
      'The tissue view could not load. Please reload to try again.';
    console.error('Unable to load the Atera kidney gallery', error);
  }
});
