# Celldega Clerk — plan and to-do

Planning settled 2026-11-06. Only the v1 proof of concept is built; everything below the
"Built" section is to do.

## What Clerk is

Clerk is an **interpretation agent and concierge for the Celldega widgets**. The user
explores; when they see something, they ask Clerk about what they are currently viewing.
It is a chat experience: it replaces taking screenshots and pasting gene lists into a
general chatbot, but Clerk sees the live state and remembers what was looked at. Clerk
does not lead the questioning unless asked.
Clerk synthesizes *existing* results across scales — tissue-level cell localization,
tissue-level expression patterns, cell morphology (H&E), tissue meta-structures, spatial
gradients, and high-dimensional analysis (unbiased clusters, gene modules, enrichment) —
into an explanation the user can check.

- **Like a law clerk:** it builds the case and the human rules. Every answer gives a chain
  of evidence, the assumptions, and the reasoning.
- **Differential diagnosis, not a verdict:** for a pattern the user noticed, Clerk lists
  competing explanations (e.g. a novel spatial program vs. crypt depth from the section
  plane vs. an artifact), says what each predicts, checks the evidence already available,
  and says which one the evidence favors and what would settle it.
- **Annotates, then scrutinizes:** proposes labels from prior-knowledge markers, but the
  emphasis is on scrutinizing labels — agreement with unbiased clusters, marker
  cleanliness across clusters and single cells, orthogonal markers that suggest
  mis-segmentation or doublets.
- **Suggests follow-ups** (enrichment, gradient, pathway, subclustering, spatial
  autocorrelation) as a concrete spec — what, why, and what result would change the
  conclusion — for the user, Clerk itself (Make tier), or another agent.
- **Not an analysis pipeline agent.** It runs analysis only to gather evidence.
- The user chooses the model, and so controls cost and context.

## Architecture

- **JS Viz API** in `celldega.js`: `getState()`, `setState()`, `snapshot()` (image + the
  state that reproduces it), and events (selection changed, view changed). It is shared by
  the notebook widgets, front-end galleries/web apps (e.g. Manifold.ai), and celldega-app.
  A web app's own agent uses this API directly and never needs to know about Clerk.
- **Thin Python mirror** of the Viz API on each widget, going through synced widget state.
- **Clerk lives in Python only.** Its core is widget-independent: state JSON + question in;
  answer / proposal / follow-up spec out. A thin notebook layer wires it to live widgets.
  celldega-app calls the core from its Python runtime (that work happens in the
  celldega-app repo). In JS, Clerk is only a presentational chat panel.
- **Agent engine:** the Claude Agent SDK for Python, driving the user's local `claude` CLI
  and its existing login (click link, paste code). Claude-only for now; keep a backend
  boundary so other LLMs/agents can be added later.
- **Two prompt sets:**
  - *Viz guide* — how to read and drive Celldega visualizations. Ships with the Viz API;
    usable by any agent; doubles as the "Celldega for agents" docs page and, later, MCP
    tool descriptions.
  - *Interpretation prompts* — Clerk's reasoning (markers, panel absence, technology
    caveats, differential-diagnosis answer format). Live with Clerk in Python.
- **Live and headless:** live = the widgets the user has open; headless = state in,
  image out, no notebook (build on `scripts/docs_screenshots/capture.py`). Same state
  format for both.
- **MCP (later):** a thin adapter over the same API — served from the kernel or app over
  local HTTP for live mode, or as a stdio server driving headless Chrome.

## Permission tiers

| Tier | What Clerk can do | Approval |
|---|---|---|
| **Look** | Read view state and snapshots; run bounded data probes on the AnnData / Matrix | Runs freely |
| **Show** | Change views, select cells, draw temporary overlays from light analysis (e.g. an alpha-shape neighborhood, regions that match the current view) | Runs freely (undoable; saving an overlay needs approval) |
| **Ask** | Give the user a task and receive the result as widget state (e.g. "label which of these 50 cells look like doublets in Yearbook") | User does it |
| **Make** | Run Celldega methods and write notebooks, only in Clerk's numbered scratch area | Explains what and why first |
| **Never** | Edit the user's notebooks or overwrite their data. Writes to the user's AnnData happen only on explicit approval, add-only (new columns), with provenance | — |

**What Clerk reads (Look tier):**

- The Landscape snapshot — the image the user sees, including the H&E — with its view state.
- Landscape's viewport summary: top genes and cluster counts for the current field of
  view. Landscape already computes these totals for its bar charts; expose them through
  the Viz API.
- The Clustergram / Matrix: the current selection, and the hierarchy — meta-clusters at the
  current dendrogram cut and gene modules.
- UniProt gene info (the same lookup Landscape makes when a gene is clicked). Use it
  liberally; cache results across calls.
- Enrich's current results.
- Bounded data probes on the AnnData / Matrix. Default to the cluster-aggregated Matrix,
  with single-cell drill-down because doublets, contamination and orthogonal markers are
  single-cell phenomena that cluster means hide. Tools compute on the full data in Python
  and return only small capped summaries (top-k markers with fold change and % expressing,
  per-gene distributions within a cluster, double-positive counts, a sample of N cell ids
  for Yearbook). Each probe is recorded so it can be rerun. Free-form pandas goes in the
  Make tier.

Clerk follows the user's observations (e.g. "these markers look asymmetric across the
goblet cells") rather than running speculative analyses on its own; heavier checks such as
spatial autocorrelation are suggested follow-ups.

**Light analysis (Show tier, temporary overlays):** define an alpha-shape neighborhood
from a cell type or set of cell types (`dega.nbhd.alpha_shape`) and show it in Landscape;
"find other regions like the one I'm looking at" (compare the viewport's cluster/gene
summary against windows across the tissue and return view states to jump to); flag cells
or regions that look contaminated.

**Follow mode (optional):** "explain the current field of view" as the user pans. Off by
default; runs only after the view settles; caches answers per view.

## Use cases, in priority order

1. **"Explain what I'm looking at / what I noticed."** "What's in this field of view?" as
   the user pans and zooms into neighborhoods. Or a pattern the user points out: e.g. HCRC
   cluster 4, where some markers look asymmetric across the goblet cells — novel spatial
   regulation, or crypt depth from slicing through crypts at an angle? Corroborate with
   where muscle and connective tissue sit under the crypts and with goblet morphology in
   the H&E. E.g. NDRG1, a subcluster-8 marker concentrated where the tissue ends look
   "dipped" → its UniProt function (stress response) + location → possibly hypoxia;
   suggest pathway/gradient follow-ups.
2. **Label scrutiny / annotation review.** The user annotates clusters with the Clustergram
   annotation tool (`manual_cat`) and asks Clerk to review them. Clerk returns a verdict per
   cluster (supported / questionable / contradicted) with its evidence: markers and %
   expressing, agreement with unbiased clusters, orthogonal markers that suggest
   mis-segmentation or doublets (Atera kidney endothelial + podocyte case), enrichment,
   spatial localization, morphology. The user accepts or edits in the Clustergram, then
   deliberately syncs the labels to the signature and single-cell AnnData (see to-do).
3. **Explain domains.** Given domain labels from other methods (e.g. SpatialFusion niches,
   BANKSY, GraphST), give evidence that each domain is meaningful — composition, markers,
   pathway scores, morphology, spatial coherence, agreement with other methods or manual
   regions — and flag hidden structure inside a domain (subclusters, spatially variable
   genes). Reference workflow: the manuscript's domain meta-analysis (IoU consensus
   domains, manual-vs-consensus overlap, consensus signatures + Enrich).
4. **Run Celldega methods and hand the user tasks** via skills (e.g. Clustergram with dot
   plot and `rank_genes_groups`; gene gradients along a tumor border; Yearbook doublet
   labeling → classifier).
5. **Guided tour of a new sample** (coarse meta-clusters → structures → markers). Lower
   priority: Clerk doesn't need to lead exploration.

## Built (v1 proof of concept)

- `dega.clerk`: `ask` / `build_prompt` / `run_claude` via the local `claude` CLI,
  single-shot, no tools; text and inline-image modes.
- `dega.viz.Clerk` chat widget; constructor linking and `link_clerk` / `landscape_clerk`.
- `Landscape.request_raster()` → `raster_png` / `raster_thumb` / `raster_view_state`
  (Python-side only).
- `CaseFile` and `_sketches.py` (to be removed; see below).

## To do — Milestone 1 (notebook, Look tier)

- [x] Safeguard: the model call runs in a background thread (`Clerk.wait()` joins it);
      Clerk takes a fresh Landscape capture when a question is asked.
- [x] Safeguard: isolated CLI call — Clerk's own system prompt, `--tools ""`,
      `--strict-mcp-config`, `--no-session-persistence`, `--setting-sources ""`, and a
      throwaway working directory. Verified live: no tools or MCP servers load and nothing
      is left behind.
- [x] Safeguard: cheaper capture — no `preserveDrawingBuffer` (forced redraw + same-task
      read), downscaled to 1024 px + 192 px preview, sent as one-off messages so images
      are never saved in notebook widget state.
- [x] Recent conversation (12 turns / 12k characters) sent with each question.
- [ ] Named widget links: Clerk links any number of widgets under names (defaulting to
      the widget's `dataset_name` / name, else type + index), refers to them by name in
      prompts, and snapshots the one the user last interacted with. The same names
      become the Viz API / MCP addresses.
- [ ] JS Viz API v0 for Landscape: `getState` / `snapshot`, including the viewport summary
      (top genes and cluster counts in view, from the totals the bar charts use).
- [x] Clustergram getter: `get_clustergram_state` (JS; `matrix.get_state(options)` on the
      instance) → rows/cols on screen (computed from the deck viewport), in ranked order,
      or by name; order per axis; marker level; dendrogram groups at the current cut;
      row/col attributes; selection (click, genes, dendrogram group, Enrich term genes,
      crop); values + dot sizes for the reported window. Python:
      `Clustergram.request_state(...)` → `latest_state` (one-off messages, not synced).
      Clerk requests it with the Landscape screenshot and adds a compact text summary to
      the prompt (`dega.clerk.format_clustergram_state`). Supersedes draft PR #296, whose
      slice API had already landed on main via #251.
- [ ] Clustergram setters, same keys as the getter: order per axis, marker level, dendrogram
      cut, select rows/cols, zoom to rows/cols, crop. Then Landscape getters/setters
      (view state, viewport summary, genes shown, cell attribute). Naming: Python widgets
      can't use `get_state` / `set_state` (ipywidgets already defines them), so Python uses
      `request_state` / `latest_state` and, for setters, e.g. `apply_state`.
- [ ] Python mirror of the Viz API v0.
- [ ] UniProt gene-info tool for Clerk: a Python mirror of Landscape's lookup (same EBI
      Proteins → UniProt REST endpoints, so names and descriptions match the UI), cached
      in memory and on disk. Works without a browser (headless, celldega-app).
- [ ] Narrated tool use: Clerk's steps stream into the chat as it works ("reading the top
      genes in view… looking up MUC2, TFF3 in UniProt… showing MUC2, TFF3 on the
      Landscape"), and it can display one or more genes on the Landscape (the
      comma-separated gene input) as it explains them.
- [x] Login check: `dega.clerk.claude_auth_status()` (runs `claude auth status --json`,
      drops email/org); a logged-out question returns log-in instructions instead of the
      CLI's raw error. Instructions are in the test notebook and on the docs page.
- [ ] Show login status in the Clerk panel when it opens. Optionally a "Log in" button
      that launches `claude auth login` on local kernels. Sign-in always completes in
      Anthropic's own flow; Celldega never sees, relays or stores credentials (the CLI
      keeps them in the OS keychain / its own credentials file).
- [x] Enrich getter: `Enrich.request_state()` → library, input genes + source, top terms
      (score, adj. p, odds ratio, genes), selected term, Enrichr link. Clerk reads it and
      skips its own Enrichr query when an Enrich panel is linked.
- [x] Clerk panel: answers render as Markdown (`js/ui/markdown.js`, escapes all text
      first), full-width panel capped at 900 px, each question shows its screenshot and
      a "Sent with" line; Clerk is told when a linked view didn't reply; genes named in
      the question or the previous answer are added to the Clustergram snapshot.
- [ ] Clerk reviews the user's Clustergram annotations (reads `manual_cat`; Look tier).
- [ ] Celldega API (useful without Clerk): copy Clustergram annotations to the signature
      AnnData (cluster-level obs) and the single-cell AnnData (cell-level obs), using the
      Matrix's `col_entity` mapping. Add-only by default (refuse to overwrite an existing
      column unless asked); unlabeled clusters → `Unassigned`; colors written to
      `uns[f"{attr}_colors"]` in category order; provenance in `uns` (source Clustergram,
      grouping column, time, whether Clerk reviewed it); refuse if the cluster ids or
      per-cluster cell counts no longer match (re-clustered since). Row annotations (gene
      modules) could sync to `var` the same way.
- [ ] Clerk core on the Agent SDK with Look-tier tools and data probes.
- [ ] Viz guide prompt + interpretation prompts (differential-diagnosis answer format).
- [ ] Export a Clerk conversation to a numbered scratch notebook.
- [ ] Remove `CaseFile` and `_sketches.py`; rewrite `docs/clerk/index.md`.
- [ ] Benchmarks (see below).

## To do — later

- [ ] Show, Ask and Make tiers; numbered notebooks with chapters and sub-chapters; Clerk
      scratch area separate from the user's notebooks.
- [ ] Light analysis: alpha-shape neighborhood from cell types; "find regions like this
      one"; contamination flags.
- [ ] Follow mode (explain the field of view as the user pans).
- [ ] Skills for running Celldega methods.
- [ ] Domain explanation (use case 3).
- [ ] Follow-up specs that another agent can execute.
- [ ] `setState` and the round-trip test: capture → restore in a fresh widget → capture →
      images match.
- [ ] Headless snapshot path; MCP server (live + headless).
- [ ] celldega-app integration (in its repo).

## To do — Landscape features Clerk builds on

- [ ] **Spatial Landscape + AnnData Zarr** (agreed; not the top priority — part of the
      longer-term work to shrink notebooks): `Landscape(base_url=<DegaFiles>,
      zarr_url=<AnnData Zarr>)` for Xenium / MERSCOPE / Visium HD etc. DegaFiles supply
      tiles, segmentation and transcripts; the Zarr supplies cell annotations (`obs`) and
      the UMAP (`obsm`), joined on cell id. Today `zarr_url` is Chromium-only and
      exclusive with `base_url`. Bonus: notebooks reference hosted annotations instead of
      embedding them in widget state.
- [ ] **Cell attribute switcher** (revives draft PR #81, which only placed a hardcoded
      `<select>`; design agreed: the ▾): a small ▾ next to the CELL toggle opens a menu of the available
      categorical cell attributes (from `adata.obs` / the Zarr `obs` / DegaFiles
      metadata); choosing one recolors cells, the bar chart and the legend. The bar
      chart title shows the active attribute. Exposed in the Viz API
      (`setState({cell_attr})`) so Clerk and other agents can switch it.
- [ ] **Compare annotations:** once labels are synced (e.g. `cell_type` next to
      `leiden` or a previous annotation), switch between them with the attribute
      switcher, and give Clerk an overlap table (annotation A × annotation B, as a
      Clustergram) to explain where and why they disagree.

## To do — make Celldega LLM-friendly

- [ ] Light copy of every docs notebook (widget state stripped; code, markdown, text output
      and small images kept), generated at docs build and linked from each notebook page.
      Docs notebooks total 413 MB; code and text are well under 1% of that.
- [ ] `llms.txt` index + markdown version of each page (`mkdocs-llmstxt`; check that it
      handles notebook pages).
- [ ] Re-run the 4 notebooks that embed the JS bundle (81 MB total; Atera kidney alone is
      43 MB) with `CELLDEGA_ESM_VERSION` set.
- [ ] "Celldega for agents" docs page = the viz guide prompt.
- [ ] Compact text summaries on widgets and Matrix (e.g. a `describe()` method) so any agent
      can read a widget's state as text.
- [ ] Publish the Viz API state format as a JSON schema.
- [ ] Longer term: notebooks load data from hosted Zarr instead of embedding it (237 MB of
      widget buffers today).

## Benchmarks

- **HCRC tutorial** (Visium HD human CRC; narrated video
  https://www.youtube.com/watch?v=IjGsIykVIUE): does Clerk reach the same conclusions —
  cluster 4 goblet, 5 plasma, 12 muscle, NDRG1 hypoxia as a hypothesis, cluster 4
  subclusters ordered by crypt depth — for the same reasons?
- **Atera kidney:** cluster 16 podocytes, 20 glomerular endothelium, endothelial + podocyte
  doublet screen.
- **Domain meta-analysis** (manuscript, mouse brain Xenium).
- **SpatialFusion CRC niches 1 vs 2** (Yates et al. 2026, bioRxiv
  10.64898/2026.03.16.712056): does Clerk explain the niches with evidence and raise
  crypt-axis sampling as an alternative explanation for the secretory vs.
  progenitor shift?
