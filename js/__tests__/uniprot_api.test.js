/* global require */

describe('UniProt multi-omic display-label parsing', () => {
  test('removes only the explicit trailing modality suffix', () => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(
        path.join(__dirname, '../external_apis/uniprot_api.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');
    const module = { exports: {} };
    const shims = `
      const base_display_label = (value) =>
        String(value ?? '').split('::', 1)[0].trim();
    `;
    const code = `${shims}\n${source}\nmodule.exports = { uniprot_query_symbol };`;
    new Function('module', 'exports', code)(module, module.exports);

    expect(module.exports.uniprot_query_symbol('CDH1::rna')).toBe('CDH1');
    expect(module.exports.uniprot_query_symbol('C38:5 PC::metabolomics')).toBe(
      'C38:5 PC'
    );
    expect(module.exports.uniprot_query_symbol('EGFR')).toBe('EGFR');
  });
});

describe('UniProt lookup timeout', () => {
  let api;
  const handleAsyncError = jest.fn();
  const original_fetch = global.fetch;

  beforeAll(() => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(
        path.join(__dirname, '../external_apis/uniprot_api.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');
    const module = { exports: {} };
    const code = `const base_display_label = (value) => String(value ?? '');
${source}
module.exports = { UNIPROT_TIMEOUT_MS, get_uniprot_info, request_uniprot_info };`;
    new Function('module', 'handleAsyncError', code)(module, handleAsyncError);
    api = module.exports;
  });

  beforeEach(() => {
    jest.useFakeTimers();
    handleAsyncError.mockClear();
    // A request that never answers (e.g. packets dropped by a firewall).
    global.fetch = jest.fn(
      (url, { signal } = {}) =>
        new Promise((resolve, reject) => {
          signal?.addEventListener('abort', () => {
            const error = new Error('The operation was aborted.');
            error.name = 'AbortError';
            reject(error);
          });
        })
    );
  });

  afterEach(() => {
    jest.useRealTimers();
    global.fetch = original_fetch;
  });

  it('gives up on a hanging request and caches the fallback text', async () => {
    const lookup = api.request_uniprot_info('NPHS1');
    jest.advanceTimersByTime(api.UNIPROT_TIMEOUT_MS);
    const info = await lookup;

    expect(info.description).toBe('Unable to obtain UniProt description.');
    expect(api.get_uniprot_info('NPHS1')).toBe(info);
    // Timeouts aren't logged.
    expect(handleAsyncError).not.toHaveBeenCalled();
  });

  it('still logs other failures', async () => {
    global.fetch = jest.fn(async () => {
      throw new Error('boom');
    });
    await api.request_uniprot_info('NPHS2');
    expect(handleAsyncError).toHaveBeenCalledTimes(1);
  });
});

describe('UniProt lookup during a service outage', () => {
  let api;
  const handleAsyncError = jest.fn();
  const original_fetch = global.fetch;

  const load = () => {
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(
        path.join(__dirname, '../external_apis/uniprot_api.js'),
        'utf8'
      )
      .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];$/gm, '')
      .replace(/^export const /gm, 'const ');
    const module = { exports: {} };
    const code = `const base_display_label = (value) => String(value ?? '');
${source}
module.exports = { UNIPROT_RETRY_MS, get_uniprot_info, has_uniprot_info,
  request_uniprot_info };`;
    new Function('module', 'handleAsyncError', code)(module, handleAsyncError);
    return module.exports;
  };

  const reply = (status, body) =>
    Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    });
  const EBI_HIT = [
    {
      accession: 'P05412',
      proteinExistence: 'Evidence at protein level',
      comments: [{}],
      gene: [{ name: { value: 'JUN' } }],
    },
  ];
  const ENTRY = {
    proteinDescription: {
      recommendedName: { fullName: { value: 'Transcription factor Jun' } },
    },
    comments: [{ texts: [{ value: 'Binds AP-1 sites.' }] }],
  };
  const SEARCH_HIT = {
    results: [
      {
        genes: [{ geneName: { value: 'JUN' } }],
        proteinDescription: ENTRY.proteinDescription,
        comments: [
          { commentType: 'FUNCTION', texts: [{ value: 'Binds AP-1 sites.' }] },
        ],
      },
    ],
  };
  // Routes: the EBI search, the UniProt entry, and UniProt's search.
  const route = ({ ebi, entry = () => reply(200, ENTRY), search }) =>
    jest.fn((url) => {
      if (url.startsWith('https://www.ebi.ac.uk/')) return ebi();
      if (url.startsWith('https://rest.uniprot.org/uniprotkb/search?')) {
        return search();
      }
      return entry();
    });

  beforeEach(() => {
    api = load();
    handleAsyncError.mockClear();
  });
  afterEach(() => {
    global.fetch = original_fetch;
    jest.restoreAllMocks();
  });

  it('looks a gene up through the EBI and its UniProt entry', async () => {
    global.fetch = route({ ebi: () => reply(200, EBI_HIT) });
    const info = await api.request_uniprot_info('JUN');
    expect(info).toEqual({
      name: 'Transcription factor Jun',
      description: 'Binds AP-1 sites.',
    });
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('falls back to UniProt search when the EBI answers 500, quietly', async () => {
    global.fetch = route({
      ebi: () => reply(500, { errorMessage: ['Internal Server Error'] }),
      search: () => reply(200, SEARCH_HIT),
    });
    const info = await api.request_uniprot_info('JUN');
    expect(info.description).toBe('Binds AP-1 sites.');
    expect(info.name).toBe('Transcription factor Jun');
    expect(handleAsyncError).not.toHaveBeenCalled();
  });

  it('retries a lookup that failed once the outage may be over', async () => {
    let now = 1000;
    jest.spyOn(Date, 'now').mockImplementation(() => now);
    global.fetch = route({
      ebi: () => reply(500, {}),
      search: () => reply(503, {}),
    });
    const failed = await api.request_uniprot_info('GSTP1');
    expect(failed.description).toBe('Unable to obtain UniProt description.');
    expect(api.has_uniprot_info('GSTP1')).toBe(true); // no refetch per hover
    expect(handleAsyncError).not.toHaveBeenCalled();

    now += api.UNIPROT_RETRY_MS;
    expect(api.has_uniprot_info('GSTP1')).toBe(false);
    global.fetch = route({
      ebi: () =>
        reply(200, [{ ...EBI_HIT[0], gene: [{ name: { value: 'GSTP1' } }] }]),
    });
    const info = await api.request_uniprot_info('GSTP1');
    expect(info.name).toBe('Transcription factor Jun');
    now += api.UNIPROT_RETRY_MS;
    expect(api.has_uniprot_info('GSTP1')).toBe(true); // a success stays
  });

  it('keeps "no UniProt match" for good', async () => {
    let now = 0;
    jest.spyOn(Date, 'now').mockImplementation(() => now);
    global.fetch = route({ ebi: () => reply(200, []) });
    const info = await api.request_uniprot_info('NOTAGENE');
    expect(info.description).toBe('Unable to obtain UniProt description.');
    now += api.UNIPROT_RETRY_MS * 10;
    expect(api.has_uniprot_info('NOTAGENE')).toBe(true);
  });
});
