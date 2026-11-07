/* global require */

// Minimal safe Markdown renderer used by the Clerk chat panel. Loaded from source
// like the other tests (no Babel transform).
const load_markdown = () => {
  const fs = require('fs');
  const path = require('path');
  const source = fs
    .readFileSync(path.join(__dirname, '../ui/markdown.js'), 'utf8')
    .replace(/^export const /gm, 'const ');
  const module = { exports: {} };
  new Function(
    'module',
    `${source}\nmodule.exports = { render_markdown, render_inline, escape_html };`
  )(module);
  return module.exports;
};

const { render_markdown, render_inline } = load_markdown();

describe('render_markdown', () => {
  test('headings, paragraphs and inline styles', () => {
    expect(render_markdown('## What the image shows')).toBe(
      '<h2>What the image shows</h2>'
    );
    expect(
      render_markdown('This is **colonic mucosa** with *goblet* cells.')
    ).toBe(
      '<p>This is <strong>colonic mucosa</strong> with <em>goblet</em> cells.</p>'
    );
    expect(render_markdown('line one\nline two\n\nnext')).toBe(
      '<p>line one<br>line two</p><p>next</p>'
    );
    expect(render_inline('~~old~~ and `MUC2`')).toBe(
      '<del>old</del> and <code>MUC2</code>'
    );
  });

  test('underscores inside names are not italics', () => {
    expect(render_inline('leiden_marker and cell_type')).toBe(
      'leiden_marker and cell_type'
    );
    expect(render_inline('a _real_ emphasis')).toBe('a <em>real</em> emphasis');
  });

  test('bullet and numbered lists, including nesting', () => {
    expect(render_markdown('- **EPCAM**\n- MUC2, TFF3')).toBe(
      '<ul><li><strong>EPCAM</strong></li><li>MUC2, TFF3</li></ul>'
    );
    expect(render_markdown('1. first\n2. second')).toBe(
      '<ol><li>first</li><li>second</li></ol>'
    );
    expect(render_markdown('- outer\n  - inner\n- next')).toBe(
      '<ul><li>outer<ul><li>inner</li></ul></li><li>next</li></ul>'
    );
  });

  test('tables, code blocks, quotes and rules', () => {
    expect(
      render_markdown('| gene | cluster |\n|---|---:|\n| MUC2 | 4 |')
    ).toBe(
      '<table><thead><tr><th>gene</th><th style="text-align:right">cluster</th></tr></thead>' +
        '<tbody><tr><td>MUC2</td><td style="text-align:right">4</td></tr></tbody></table>'
    );
    expect(render_markdown('```\na < b\n```')).toBe(
      '<pre><code>a &lt; b</code></pre>'
    );
    expect(render_markdown('> quoted')).toBe(
      '<blockquote><p>quoted</p></blockquote>'
    );
    expect(render_markdown('---')).toBe('<hr>');
  });

  test('links: only http(s) and mailto survive', () => {
    expect(render_inline('[UniProt](https://www.uniprot.org)')).toBe(
      '<a href="https://www.uniprot.org" target="_blank" rel="noopener noreferrer">UniProt</a>'
    );
    expect(render_inline('[x](javascript:alert(1))')).not.toContain('<a');
  });

  test('raw HTML in the model output is escaped, never rendered', () => {
    const html = render_markdown(
      '<img src=x onerror="alert(1)"> **bold** <script>alert(1)</script>'
    );
    expect(html).not.toMatch(/<img|<script/);
    expect(html).toContain('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
    expect(html).toContain('<strong>bold</strong>');

    const link = render_inline('[a](https://x.org" onmouseover="alert(1))');
    expect(link).not.toMatch(/" onmouseover="/);
  });
});
