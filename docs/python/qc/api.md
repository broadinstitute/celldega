# QC Module (in development)

!!! warning "In development"
    `celldega.qc` is not part of the documented API yet. Its functions may change
    or be removed without deprecation, and calling `qc_segmentation` or
    `orthogonal_expression_calc` raises a warning. The plan below describes where
    the module is headed.

## What it does today

- `qc_segmentation` writes cell-level and gene-level metrics for one
  segmentation of a Xenium, MERSCOPE or custom dataset: the share of transcripts
  assigned to cells, cell counts and areas, and transcripts and genes per cell.
- `orthogonal_expression_calc` compares segmentations by how often cells of one
  type contain transcripts of another type's marker genes.

Both read instrument output folders directly rather than `AnnData`.

## Future directions: ectopic expression

Spatial data let you check cells by eye, and one of the most useful checks is
**ectopic expression**: a cell expressing marker genes of a different cell
type, for example podocin (NPHS2) in a glomerular endothelial cell next to a
podocyte. Ectopic expression can come from transcripts spilling over from a
neighboring cell, from two cells segmented as one, or from real biology. The
plan is to rebuild `qc` around it, replacing the two functions above.

1. **Calculate a cell type × marker set matrix.** Inputs: cell-level `AnnData`,
   a cell-type column, and marker sets from prior knowledge (a dictionary, a
   `.gmt` gene-set file, or marker ranks). Entry (A, B) is how much cells of
   type A express type B's markers, such as the fraction of type-A cells with at
   least `k` type-B marker counts. The diagonal is on-target expression; the
   off-diagonal entries are ectopic.
2. **Add spatial context.** For each ectopic cell, record how many of its
   spatial neighbors are of type B. Ectopic expression explained by neighbors
   suggests spillover or segmentation error; unexplained ectopic expression
   suggests doublets or biology. This can be a second layer, shown as dot size.
3. **Show it as a square Clustergram.** Clustering groups cell types that share
   ectopic patterns, such as cell types that sit next to each other in the
   tissue.
4. **Review cells in a linked Yearbook.** Clicking an off-diagonal entry (A, B)
   selects type-A cells ranked by their type-B marker expression with
   `celldega.select`, and pages them in a Yearbook with one marker of each type
   highlighted. Flagged cells come back to Python.
5. **Compare segmentations.** One matrix per segmentation, side by side,
   replaces today's `qc_segmentation` comparison.

A possible API:

```python
ectopic = dega.qc.calc_ectopic_expression(
    adata, cell_type="cell_type", markers=markers, min_counts=3, n_neighbors=10
)  # cell types x marker sets, with a neighbor-explained layer
mat = dega.clust.Matrix(ectopic)
mat.cluster()
dega.viz.Clustergram(matrix=mat)

review = dega.qc.select_ectopic(adata, source="Glomerular endothelium", target="Podocytes", markers=markers)
dega.viz.Yearbook(base_url=degafiles_url, cells=review.names())
```

Until then, the [ectopic expression review](../../examples/brief_notebooks/Atera_Kidney_Ectopic_Expression_Review.ipynb)
shows the review step with `celldega.select` and Yearbook.

## API

::: celldega.qc
