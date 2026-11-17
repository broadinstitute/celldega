/**
 * Minimal, safe Markdown -> HTML for chat answers (e.g. Clerk).
 *
 * Every piece of text is HTML-escaped before any markup is added, so model output
 * cannot inject tags, attributes or scripts; the only markup in the result is what
 * this module produces. Links are kept only for http(s) and mailto URLs, plus
 * in-app `view:` links (class `clerk-view`, no navigation).
 *
 * Supported: headings, paragraphs (single newlines become line breaks), bold,
 * italic, strikethrough, inline code, fenced code blocks, bullet and numbered lists
 * (nested by indentation), blockquotes, horizontal rules, GitHub-style tables, and
 * [text](url) links.
 */

export const escape_html = (text) =>
  String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const SAFE_URL = /^(https?:\/\/|mailto:)/i;
// In-app links to a view Clerk cited, e.g. [Fig 1A](view:1A); the panel decides
// what clicking one does.
const VIEW_URL = /^view:([A-Za-z0-9_.-]{1,32})$/;

/** Inline Markdown on one piece of text: escape first, then add markup. */
export const render_inline = (text) => {
  // Protect code spans from the other rules.
  const code_spans = [];
  let html = escape_html(text).replace(/`([^`]+)`/g, (_match, code) => {
    code_spans.push(code);
    return `\uE000${code_spans.length - 1}\uE000`;
  });

  html = html
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (match, label, url) => {
      const view = VIEW_URL.exec(url);
      if (view) {
        return `<a class="clerk-view" href="#" data-view="${view[1]}">${label}</a>`;
      }
      return SAFE_URL.test(url)
        ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`
        : match;
    })
    .replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, '<strong>$1</strong>')
    .replace(/__(?=\S)([\s\S]*?\S)__/g, '<strong>$1</strong>')
    .replace(/~~(?=\S)([\s\S]*?\S)~~/g, '<del>$1</del>')
    .replace(/(^|[^*\w])\*(?=\S)([^*]*?\S)\*(?!\*)/g, '$1<em>$2</em>')
    // Underscores italicize only at word boundaries, so gene and attribute names
    // such as leiden_marker are left alone.
    .replace(/(^|[^_\w])_(?=\S)([^_]*?\S)_(?![_\w])/g, '$1<em>$2</em>');

  return html.replace(
    /\uE000(\d+)\uE000/g,
    (_match, index) => `<code>${code_spans[Number(index)]}</code>`
  );
};

const FENCE = /^\s*(```|~~~)/;
const HEADING = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const RULE = /^\s{0,3}([-*_])(\s*\1){2,}\s*$/;
const QUOTE = /^\s{0,3}>\s?(.*)$/;
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const TABLE_DIVIDER = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

const split_row = (line) =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((cell) => cell.trim());

const render_table = (lines) => {
  const header = split_row(lines[0]);
  const aligns = split_row(lines[1]).map((cell) => {
    if (cell.startsWith(':') && cell.endsWith(':')) return 'center';
    if (cell.endsWith(':')) return 'right';
    return null;
  });
  const cell = (tag, text, i) => {
    const align = aligns[i] ? ` style="text-align:${aligns[i]}"` : '';
    return `<${tag}${align}>${render_inline(text)}</${tag}>`;
  };
  const body = lines
    .slice(2)
    .map(
      (line) =>
        `<tr>${split_row(line)
          .map((text, i) => cell('td', text, i))
          .join('')}</tr>`
    )
    .join('');
  return `<table><thead><tr>${header
    .map((text, i) => cell('th', text, i))
    .join('')}</tr></thead><tbody>${body}</tbody></table>`;
};

const render_list = (items) => {
  // items: [{indent, ordered, text}] -> nested <ul>/<ol>, children inside the
  // parent <li>.
  let html = '';
  const stack = [];
  const close_level = () => {
    html += `</li></${stack.pop().tag}>`;
  };
  items.forEach(({ indent, ordered, text }) => {
    const tag = ordered ? 'ol' : 'ul';
    while (stack.length && indent < stack[stack.length - 1].indent) {
      close_level();
    }
    const top = stack[stack.length - 1];
    if (!top || indent > top.indent) {
      stack.push({ indent, tag });
      html += `<${tag}><li>`;
    } else if (top.tag !== tag) {
      close_level();
      stack.push({ indent, tag });
      html += `<${tag}><li>`;
    } else {
      html += '</li><li>';
    }
    html += render_inline(text);
  });
  while (stack.length) close_level();
  return html;
};

/**
 * Render Markdown to safe HTML.
 * @param {string} markdown
 * @returns {string} HTML containing only markup produced here.
 */
export const render_markdown = (markdown) => {
  const lines = String(markdown ?? '')
    .replace(/\r\n?/g, '\n')
    .split('\n');
  const blocks = [];
  let paragraph = [];

  const flush_paragraph = () => {
    if (paragraph.length) {
      blocks.push(`<p>${paragraph.map(render_inline).join('<br>')}</p>`);
      paragraph = [];
    }
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    if (FENCE.test(line)) {
      flush_paragraph();
      const fence = line.trim().slice(0, 3);
      const code = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith(fence)) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1; // closing fence (or end of input)
      blocks.push(`<pre><code>${escape_html(code.join('\n'))}</code></pre>`);
      continue;
    }

    if (!line.trim()) {
      flush_paragraph();
      i += 1;
      continue;
    }

    const heading = line.match(HEADING);
    if (heading) {
      flush_paragraph();
      const level = heading[1].length;
      blocks.push(`<h${level}>${render_inline(heading[2])}</h${level}>`);
      i += 1;
      continue;
    }

    if (RULE.test(line) && !LIST_ITEM.test(line.replace(RULE, ''))) {
      flush_paragraph();
      blocks.push('<hr>');
      i += 1;
      continue;
    }

    if (
      line.includes('|') &&
      i + 1 < lines.length &&
      TABLE_DIVIDER.test(lines[i + 1])
    ) {
      flush_paragraph();
      const table = [line, lines[i + 1]];
      i += 2;
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        table.push(lines[i]);
        i += 1;
      }
      blocks.push(render_table(table));
      continue;
    }

    if (QUOTE.test(line)) {
      flush_paragraph();
      const quoted = [];
      while (i < lines.length && QUOTE.test(lines[i])) {
        quoted.push(lines[i].match(QUOTE)[1]);
        i += 1;
      }
      blocks.push(
        `<blockquote>${render_markdown(quoted.join('\n'))}</blockquote>`
      );
      continue;
    }

    if (LIST_ITEM.test(line)) {
      flush_paragraph();
      const items = [];
      while (i < lines.length) {
        const item = lines[i].match(LIST_ITEM);
        if (item) {
          items.push({
            indent: item[1].replace(/\t/g, '    ').length,
            ordered: /\d/.test(item[2]),
            text: item[3],
          });
          i += 1;
        } else if (lines[i].trim() && /^\s+/.test(lines[i]) && items.length) {
          // Indented continuation of the previous item.
          items[items.length - 1].text += ` ${lines[i].trim()}`;
          i += 1;
        } else if (
          !lines[i].trim() &&
          i + 1 < lines.length &&
          LIST_ITEM.test(lines[i + 1])
        ) {
          i += 1; // blank line between items of the same list
        } else {
          break;
        }
      }
      blocks.push(render_list(items));
      continue;
    }

    paragraph.push(line.trim());
    i += 1;
  }
  flush_paragraph();
  return blocks.join('');
};
