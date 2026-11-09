/* global require */

// Row labels keep their beginning and end with "…" when they don't fit.
describe('fit_label', () => {
  let fit_label;
  let ELLIPSIS;
  let LABEL_CHARACTER_SET;

  beforeAll(() => {
    // A canvas whose text is 6 px per character (7 when bold).
    const real_create = document.createElement.bind(document);
    jest.spyOn(document, 'createElement').mockImplementation((tag) => {
      if (tag !== 'canvas') return real_create(tag);
      const context = {
        font: '',
        measureText: (text) => ({
          width: text.length * (context.font.startsWith('bold') ? 7 : 6),
        }),
      };
      return { getContext: () => context };
    });
    const fs = require('fs');
    const path = require('path');
    const source = fs
      .readFileSync(
        path.join(__dirname, '../deck-gl/matrix/label_fit.js'),
        'utf8'
      )
      .replace(/^export const /gm, 'const ');
    ({ fit_label, ELLIPSIS, LABEL_CHARACTER_SET } = new Function(
      `${source}\nreturn { fit_label, ELLIPSIS, LABEL_CHARACTER_SET };`
    )());
  });

  afterAll(() => jest.restoreAllMocks());

  test('a label that fits is unchanged', () => {
    expect(fit_label('MUC2', 60, 12)).toBe('MUC2'); // 24 px
  });

  test('a long label keeps its beginning and ends with an ellipsis', () => {
    const fitted = fit_label('MUC2 (Goblet cells)', 60, 12);
    expect(fitted).toBe('MUC2 (Gob…');
    expect(fitted.length * 6).toBeLessThanOrEqual(60);
    // No space is left dangling before the ellipsis.
    expect(fit_label('MUC2 (Goblet cells)', 36, 12)).toBe('MUC2…');
  });

  test('bold labels are measured in bold', () => {
    expect(
      fit_label('MUC2 (Goblet cells)', 60, 12, { font_weight: 'bold' })
    ).toBe('MUC2 (G…');
  });

  test('no room leaves just the ellipsis; no layout leaves the label alone', () => {
    expect(fit_label('MUC2', 3, 12)).toBe(ELLIPSIS);
    expect(fit_label('MUC2 (Goblet cells)', Number.NaN, 12)).toBe(
      'MUC2 (Goblet cells)'
    );
    expect(fit_label('', 10, 12)).toBe('');
  });

  test('the label layers can draw the ellipsis', () => {
    expect(LABEL_CHARACTER_SET).toContain(ELLIPSIS);
    expect(LABEL_CHARACTER_SET).toContain('A');
    expect(LABEL_CHARACTER_SET).toContain(' ');
  });
});
