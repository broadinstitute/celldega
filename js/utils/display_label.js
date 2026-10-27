/**
 * Return the human-readable portion of a Celldega display label.
 *
 * Stacked multi-omic matrices keep distinct internal feature IDs with a
 * ``::modality`` suffix (for example, ``CDH1::rna``). The suffix is metadata,
 * not part of the gene, protein, or metabolite name. UI text can therefore use
 * the base label while selection and data operations continue to use the full
 * identifier. A single colon is deliberately preserved for names such as
 * ``C38:5 PC``.
 */
export const base_display_label = (value) =>
  String(value ?? '')
    .split('::', 1)[0]
    .trim();
