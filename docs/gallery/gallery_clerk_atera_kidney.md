# Clerk Case: Atera Kidney Cell Types

A conversation with [Clerk](../visualizations/clerk/index.md), Celldega's AI tool for
interpreting its visualizations, about the 28 default Leiden clusters of an Atera v1
whole-transcriptome section of non-diseased human kidney (FFPE). A scientist asked
Clerk which cell types the clusters are. Clerk read the Clustergram's marker genes,
looked them up in Enrichr, proposed tentative cell types with their evidence, and,
when asked, labeled them on the Clustergram: cell types on its columns, and the marker
genes behind them on its rows.

Clerk's cell types are tentative: each is its reading of the evidence it was shown,
recorded with a confidence for the scientist to accept, edit or reject.

Read the conversation on the right, one question at a time. Click a gene to color the
cells by its expression, a cluster to highlight its cells, a cited view (*Fig 1A*) to
show what Clerk pointed to, or **Show this view** under a question to return to the
view it was asked about. This is a saved conversation: nothing here is sent to Claude.

The conversation and the Clustergram's Matrix load from the
[case folder on Hugging Face](https://huggingface.co/datasets/broadinstitute/Celldega_Supporting_Data/tree/main/clerk/atera_kidney),
and the tissue view streams images, cell boundaries, transcripts and gene expression
from [DegaFiles on GitHub](https://github.com/broadinstitute/Celldega_Atera_v1_WTA_Kidney_non_diseased_FFPE).
To reopen the same case in Python, see the
[Clerk case notebook](../examples/brief_notebooks/Atera_Kidney_Clerk_Case.ipynb).

<div class="linked-gallery clerk-gallery" data-clerk-gallery="atera-kidney">
  <div class="linked-landscape-panel">
    <p data-clerk-status="landscape" role="status" hidden>Loading the tissue… The first load may take a moment.</p>
    <div data-clerk-landscape aria-label="Atera kidney tissue view"></div>
  </div>
  <div class="linked-clustergram-panel">
    <p data-clerk-status="clustergram" role="status" hidden>Loading the cluster signatures…</p>
    <div data-clerk-clustergram aria-label="Atera kidney cluster Clustergram with cell-type labels"></div>
  </div>
  <div class="clerk-gallery-panel">
    <p data-clerk-status="clerk" role="status" hidden>Loading the conversation…</p>
    <div data-clerk-panel aria-label="Saved Clerk conversation"></div>
  </div>
</div>
