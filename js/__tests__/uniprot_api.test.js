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
