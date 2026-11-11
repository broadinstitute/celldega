# Celldega Clerk — plan and to-do

Planning started 2026-11-06. Checked items below are implemented; unchecked items are
planned. The architecture section describes the target, not the current boundaries.

## Review checkpoint: two deliverables (2026-11-08)

The reusable Viz API and the Clerk POC are separate deliverables. Manual users and
other agents must be able to save and restore views without constructing a Clerk.
Recommended acceptance gates before expanding the POC:

- **Viz API:** separate bounded scientific observations from complete supported view
  settings. Give saved records a versioned schema, dataset identity, software version,
  capture options and explicit restoration coverage. Reject incompatible records
  instead of silently applying them to different data. Return image and state from
  one coordinated capture, with a completion/error contract for setters.
- **Round trips:** capture → change → restore → capture for manual and agent workflows,
  including linked widgets and a fresh instance. Require equal supported state and
  equivalent rendered output. The current browser checks cover camera/order/crop and
  layer/channel/slider restoration on the same loaded instances. The JS-only example
  additionally checks fresh-instance Clustergram replay and data/schema rejection;
  cross-renderer-version pixel equivalence remains open.
- **Clerk POC:** demonstrate one bounded loop: explain a view, inspect evidence, show a
  cited view, return to the user's view, export, reopen. Preserve the observations and
  lookup results used for the answer, distinguishing measurements, estimates and
  model interpretation. A browser timeout or failed setter must fail the action.
- **Architecture:** keep the API and saved-view format independent of Clerk. The
  bounded turn loop now lives in `clerk/engine.py` and exchanges plain-data events.
  `viz/widget.py` supplies notebook transport, model calls and UI; the report builder
  is also independent. `docs/clerk/hosting.md` maps the same boundary onto the inspected
  celldega-app renderer, scoped window registry and Python worker.

Implemented in this follow-up: a `celldega.view` v2 saved-view envelope, same-task
image/state capture, name-based data identity (cell, gene and cluster-label names, or a
Clustergram's row and column names) with an optional producer-declared
`data_revision`, restore compatibility checks, a local dataset revision helper,
manual/Clerk capture through the same API, screenshots as PNGs with the saved view
embedded (reopened with `from_png`), and fresh-instance JS browser checks. Remaining
replay coverage is documented in the Viz API.

Batch annotation, Make-tier execution, report chapters, video and MCP can remain
follow-on work until these gates hold. Supporting another model backend does not
need to block either deliverable.

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

- **JS Viz API** in `celldega.js`: `get_state()`, `apply_state()`, `snapshot()` and
  `restore_snapshot()`, with selection/view events planned. It is shared by
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
- Reports collect versioned saved views and the reasoning that cites them.

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
- [x] Recent conversation sent with each question: last `history_questions` (10) questions
      within `history_chars` (40k), configurable per panel (was 12 messages / 12k chars).
- [ ] Named widget links: Clerk links any number of widgets under names (defaulting to
      the widget's `dataset_name` / name, else type + index), refers to them by name in
      prompts, and snapshots the one the user last interacted with. The same names
      become the Viz API / MCP addresses.
- [x] JS Viz API v0 for Landscape: `get_state` / `apply_state` / `capture_raster`,
      including the viewport summary. A coordinated image + state snapshot is pending.
- [x] Clustergram getter: `get_clustergram_state` (JS; `matrix.get_state(options)` on the
      instance) → rows/cols on screen (computed from the deck viewport), in ranked order,
      or by name; order per axis; marker level; dendrogram groups at the current cut;
      row/col attributes; selection (click, genes, dendrogram group, Enrich term genes,
      crop); values + dot sizes for the reported window. Python:
      `Clustergram.request_state(...)` → `latest_state` (one-off messages, not synced).
      Clerk requests it with the Landscape screenshot and adds a compact text summary to
      the prompt (`dega.clerk.format_clustergram_state`). Supersedes draft PR #296, whose
      slice API had already landed on main via #251.
- [x] Clustergram setters, first batch: `Clustergram.apply_state({...})` for the controls
      the front end already takes from Python — `marker_level` (DIM, via `rank_dim`),
      `mode` (heatmap/dotplot), `size` (PROP/UNIT), `focus_gene` (search-style zoom).
      Validates everything before changing anything. The snapshot reports `display`
      (mode, size, focused gene) so Clerk sees the result.
- [x] Clerk actions (interim, before the Agent SDK): Clerk may end an answer with a
      ```` ```celldega-actions ```` JSON block using the `apply_state` keys; the kernel
      applies it, re-captures the views and asks Clerk to continue (≤
      `max_action_rounds`, default 2). Changes show in the chat as "↻ Changed …". The
      same setters become Agent SDK tools later.
- [x] Instructions rewrite (`clerk/prompts.py`): brief answers; conservative (check a
      cluster's top ~25 markers, canonical + alternative markers, >1 enrichment library
      before a confident call); morphology/anatomy first; the sample's diagnosis isn't
      the region's; no abnormality claims without specific evidence.
- [x] Read-only lookups for Clerk: ranked markers per cluster (Matrix sends
      `viz["markers"]` to the front end; snapshot option `markers`), genes, Enrichr
      (Python client, `dega.clerk.lookups.enrichr`), PubMed (NCBI E-utilities,
      `dega.clerk.lookups.pubmed`). Up to 3 lookup/change rounds per question.
- [x] Findings: Clerk records proposed cell types (`celldega-findings` block) →
      `clerk.findings_df()`, `clerk.write_cell_types(adata, groupby, key)` (add-only,
      provenance in `uns`).
- [x] Manual categories settable from Python: `Clustergram.set_categories(...)` /
      `apply_state({"categories": ...})` (front end applies them like the editor,
      `js/matrix/manual_categories.js`). Clerk writes recorded cell types to the
      manual column category, never overwriting the scientist's labels.
- [x] Landscape getters/setters: `Landscape.apply_state` (clusters, genes, view,
      zoom_to, reset_view, space), `request_state` (space, camera, coloring, selection,
      field-of-view cluster/gene counts), `neighborhood_summary()` (drawn regions' cell
      count + cluster mix). Clerk can drive the Landscape and waits for changes (e.g.
      gene loading) before its next screenshot.
- [x] Model effort setting (`clerk.effort`, panel picker; CLI `--effort`).
- [x] Landscape layer toggles and sliders (2026-11-08): `layers`, `channels`,
      `sliders`, `image_source` in JS and Python; getters and screenshot replay retain
      them. Image-toggle state is per instance. Browser restoration matched both
      state and rendered PNG for image channels and layer/slider settings.
- [x] Clustergram navigation (2026-11-08): `view`, `crop`, `order` in JS and Python.
      Crop and custom orders use stable names across the full axes, independently of
      observation caps. Replay applies order/crop before camera. Browser restoration
      matched state and rendered PNG for independent axis zoom, pan, crop and order.
- [ ] Sync labels through the Clustergram to the signature and single-cell AnnData
      (Clerk's `write_cell_types` covers its own findings).
- [ ] Every control API-controllable. Clustergram setters still needing front-end
      handlers: dendrogram cut per axis, select a dendrogram branch / column / gene label
      (which drives linked Landscape + Enrich), semantic zoom to rows/cols, category
      dropdown. Landscape still needs selected cell IDs and XY axis controls; Enrich
      needs library, term count and term selection setters. Naming:
      Python widgets can't use `get_state` / `set_state` (ipywidgets defines them), so
      Python uses `request_state` / `latest_state` / `apply_state`.
- [x] Viz API documented as its own page (2026-11-08): docs/javascript/viz-api.md —
      getters / setters / exporters, JS and Python side by side, state shapes, keys,
      reproduction, what's not settable yet. JS gained the setters it lacked:
      `clustergram.apply_state` (same keys/validation as Python) and
      `clustergram.set_categories`; Landscape `apply_state` now accepts `space` and
      rejects unknown keys. Meant to outlast Clerk (other agents, e.g. Manifold).
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
- [x] Export / case record (2026-11-07): `clerk.record` (per question: model, effort,
      sent-with, steps, each capture's full PNG + `apply_state` reproduction for Landscape
      and Clustergram); `clerk.export(folder, adata=, groupby=)` → `report.html` (nbconvert,
      screenshots under their reproduction code, Work/Evidence collapsed), `report.ipynb`,
      `record.json` + `images/`, `findings.csv`, annotated AnnData. Builder is
      widget-independent (`clerk/report.py`) for celldega-app.
- [x] Panel turns (2026-11-07): collapsible turn per question, "Work · N steps" folded,
      Evidence folded, Yes button for a closing yes/no question, Continue button at the
      round cap, Expand/Collapse all, Export button.
- [x] Action loop (2026-11-07): 6 rounds then pause + Continue (resumable workstream);
      identical consecutive actions skipped; view changes end the reply unless
      `"continue": true`; lookup results accumulate over a question (24k-char cap).
- [x] Marker genes Clerk cites are marked on Clustergram rows (manual row category or
      `clerk_marker`) with the cell type, same color as the column; scientist's labels kept;
      a relabeled cluster's old marks cleared.
- [ ] "Label my clusters" recipe: code gathers top-25 markers for every cluster + Enrichr
      (two libraries) per cluster + composition in view, then one model call proposes all
      labels with evidence. Panel button. Cheaper and more reproducible than model-driven
      rounds for a predictable batch job.
- [ ] Mid-zoom survey without transcripts: cluster counts in view from cell positions
      (always loaded), gene estimates from cluster signatures (the linked Clustergram's
      Matrix, or the `viewport_summary.js` estimate route); each count flagged measured vs
      estimated in the Landscape snapshot, and Clerk says when it uses estimates.
- [ ] Yearbook link: Clerk requests portraits (e.g. 12 cluster-16 cells with high NPHS1 +
      EMCN) for doublet / segmentation checks; the scientist labels them; Clerk reads back.
- [x] Prompt caching (2026-11-07): one CLI session per question (`clerk.Session`,
      `--session-id` then `--resume`); follow-up rounds send only new lookups / changed
      views / a new screenshot. Measured: follow-up on a 34k-token prompt $0.008 vs
      $0.12 (old rebuilt prompts paid a cache *write* every round and never read it).
      Transcripts deleted on close; stale ones swept. Usage per question in the record.
- [x] Isolation audit (2026-11-07): probe shows the CLI adds only userEmail + currentDate;
      no memory / CLAUDE.md / prior sessions. Added CLAUDE_CODE_DISABLE_AUTO_MEMORY and
      CLAUDE_CODE_DISABLE_CLAUDE_MDS. Prompt examples were colon-specific (cluster 4 →
      Goblet cells matched the HCRC test data!) → replaced with placeholders. Docs:
      "What Clerk knows" (training knowledge of public datasets is the remaining caveat).
- [x] Clustergram screenshots: `_RasterCapture` mixin shared with Landscape;
      `cgm.request_raster()`, `matrix.capture_raster()`; Clerk records them (not sent to
      the model) and the report shows them under `cgm.apply_state(...)`.
- [x] **Evidence links, v1** (2026-11-07): genes (UniProt hover; click → Landscape
      genes + Clustergram highlight/focus; shift-click adds), "cluster N" (label hover;
      click → Landscape highlight), "N genes" in work lines (hover lists; click shows),
      cited views (`celldega-views` block + `[Fig 1A](view:1A)`; validated against
      `VIEW_KEYS`; hover caption; click applies). Clicks work while Clerk answers; the
      scientist's view is saved on the first click and RETURN restores it.
      Reports: cited views → numbered figures with reproduction code (no images yet).
      Prompt: Clerk cites views instead of changing them. Yes/No buttons; widget-style
      all-caps text buttons.
- [x] **Screenshots with provenance** (2026-11-07): `widget.screenshot(description, path)`
      on Landscape / Clustergram / CellCloud / NeighborhoodCloud, `dega.viz.screenshot(linked,
      ...)` (side-by-side composite), the **PIC** text button in their control panels
      (dialog: title + description). Writes PNG (record embedded as iTXt) + .json + .md
      (description, image, apply_state code, data sources). `screenshot_metadata` for what
      Python can't see (AnnData path). Clerk: `snapshot` action (author "Clerk"),
      `clerk.screenshots`, and `load_briefing(folder | png)` reads screenshots.
      Matrix.read_zarr records its source. Module `viz/screenshots.py`.
- [x] Evidence retention and replay corrections (2026-11-08): manual screenshots retain
      `observed_state`; Clerk captures retain scientific observations and available
      source metadata, including changed values when the camera is unchanged. Exports
      explicitly mark partial restoration. UMAP/XY gene summaries carry estimate vs
      dataset scope into the API and prompt. Failed/timed-out browser applies no longer
      become successful action records. Data fingerprints, atomic capture and full
      annotation/selection replay remain open.
- [ ] Screenshots, next: re-render saved screenshots at any size / aspect ratio for paper
      figures (headless, from the record; reuse scripts/docs_screenshots/capture.py);
      **GIFs first, then video**: a sequence of states (toggle, zoom, click through genes)
      rendered as frames, since the interaction is often the argument; include control
      panels optionally (DOM capture); a scrapbook/gallery view of a screenshot folder
      with click-to-restore; drag a screenshot PNG onto a widget to restore its state.
- [ ] Evidence links, next: render each cited view to images on export (visit → capture
      Landscape + Clustergram → restore); cell-type labels and neighborhoods as links;
      Yearbook selections as links once Yearbook is linked.
- [ ] (original plan) **Evidence links ("Fig 1A")** — Clerk's answers cite views: Clerk declares named
      views in its reply (`{"views": {"1A": {"landscape": {...}, "clustergram": {...},
      "caption": "..."}}}`, the same `apply_state` dicts, validated in Python) and links
      to them in text (`[Fig 1A](view:1A)`). Panel renders them as blue links; clicking
      applies the view to the linked widgets (via Python, so widgets in other cells
      work). Genes and clusters in answers auto-link (click → color the Landscape by the
      gene(s) / highlight the cluster; focus the Clustergram row). Report: each figure is
      rendered once on export (visit view → capture both widgets → restore) and links
      jump to the static figure, with its reproduction code. Reads like a short paper.
- [ ] **Story notebooks** — a ClerkReport as a tutorial-style notebook: markdown-looking
      cells that are small widgets with view links bound to the notebook's widgets
      (front-end links so they work in exported docs without a kernel). One case = one
      line of inquiry (e.g. HCRC overview; sub-clustering as a second case).
- [x] **Briefings from earlier cases** (2026-11-07) — `clerk.briefing` (text) /
      `clerk.load_briefing(folder | record.json | .md | Clerk, append=)`: a labeled
      "Earlier work" prompt section (claims to check, not evidence), a "Briefing: …" line
      in the panel, shown in exported reports. Off by default; never implicit memory.
- [ ] **Fast by default, deeper on request** — measured at low effort on a ~1.7k-token
      prompt: Haiku 7.5 s (verbose), Sonnet 4.8 s, Opus 5.1 s; effort and the number of
      rounds matter more than model size. Option: default Sonnet + low effort and a
      "Go deeper" button that re-asks with Opus + high effort (answer labeled by model).
- [ ] Upload the Atera kidney Matrix (local cache
      `notebooks/data/atera_data/<sample>/kidney_leiden_marker_matrix.zarr`, 40 MB, verified
      over HTTP) to `Atera/Atera_v1_WTA_Kidney_non_diseased_FFPE/kidney_leiden_markers.zarr`
      on the HF dataset; deferred (needs a token with broadinstitute write access). The
      Clerk kidney notebook already tries that URL first.
- [ ] **Celldega primer** — a versioned knowledge pack in the system prompt (cached
      across questions once above the minimum cache size): how to read each view (DIM,
      dot size, z-scores), technology specifics (bins vs cells, panel size, segmentation
      spillover, ambient RNA), which lookup answers which question. General know-how
      only, no tissue answers (see the placeholder rule). Doubles as the "Celldega for
      agents" docs page.
- [x] Remove obsolete CaseFile/sketch prototypes; document saved views and higher-level reports.
- [ ] Benchmarks (see below).

## Guiding principles (from planning notes, 2026-11-07)

- Priority: make the Claude Clerk useful and robust on real benchmark datasets. No
  provider abstraction, MCP or agent framework until the native experience proves out.
- Celldega is visualization + biological abstractions + deterministic analysis +
  interpretation; Clerk consumes the same abstractions scientists use. When Clerk needs
  something, ask whether it exposes a missing Celldega primitive (viewport summary,
  population summary, saved-view reference, Yearbook selection) and build that.
- Viz API: what are you showing, what can be applied, can it be saved and restored.
  Compact, semantic, validated state; inspect vs navigate vs annotate kept separate;
  scientist annotations protected; round-trip tests for important states.
- Evidence provenance in reports: observed, derived, prior knowledge, model inference,
  human judgment. Reports evolve toward chapters per population with supporting and
  contradicting evidence, alternatives, unresolved questions and the human ruling.
- Cost: deterministic analysis before model reasoning; entity-level summaries over raw
  data; images only when pixels add information; session continuation; batch
  predictable workflows; keep stable knowledge cacheable.
- Next in order: round-trip tests; a "review N populations → one chapter each" report
  workflow; a small versioned Celldega/assay primer; a structured cell-type signature
  format (positive/negative markers, alternatives, panel caveats); Yearbook as the
  human adjudication step.

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
