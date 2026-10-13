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
