# Clerk Module API Reference

The `clerk` module is the backend for **Celldega Clerk** — an LLM assistant that helps
interpret clusters and regions of spatial-transcriptomics data. It talks to Claude via
the local `claude` CLI (kernel-side, no API key) and reasons single-shot from evidence
that Celldega pre-gathers. The paired visualization is
[`celldega.viz.Clerk`](../viz/api.md#celldega.viz.widget.Clerk).

See the [Clerk guide](../../clerk/index.md) for a walkthrough and code snippets.

::: celldega.clerk
