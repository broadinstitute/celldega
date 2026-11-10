# Clerk Module API Reference

The `clerk` module is the backend for **Clerk AI**, an AI assistant that helps interpret
clusters and regions of spatial and single-cell data. It talks to Claude through the
local `claude` CLI (kernel-side, no API key) and reasons from the evidence Celldega
gathers: the linked views, and the lookups it asks for (ranked markers, Enrichr,
PubMed). The paired widget is [`celldega.viz.Clerk`](../viz/api.md#celldega.viz.widget.Clerk).

See the [Clerk AI guide](../../clerk/index.md) for a walkthrough and code snippets.

::: celldega.clerk
