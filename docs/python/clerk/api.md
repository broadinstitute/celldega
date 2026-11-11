# Clerk Module API Reference

The `clerk` module is the backend for **Clerk**, Celldega's AI tool for exploring and
interpreting its visualizations. It isn't an MCP server: it's the prompts, actions and
lookups that let Claude read and drive linked Celldega widgets and consult outside tools
(Enrichr, PubMed). It talks to Claude through the local `claude` CLI (kernel-side, no API
key) and reasons from the evidence Celldega gathers: the linked views, and the lookups
it asks for (ranked markers, Enrichr, PubMed). The paired widget is
[`celldega.viz.Clerk`](../viz/api.md#celldega.viz.widget.Clerk); lay it out beside
linked views with `dega.viz.spatial_clustergram(..., clerk=True)`.

See the [Clerk guide](../../visualizations/clerk/index.md) for a walkthrough and code snippets.

::: celldega.clerk
