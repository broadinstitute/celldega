# Hosting the bounded Clerk workflow

`celldega.clerk.run_turn` implements the bounded interpretation/evidence loop without
widget traits, a browser transport or a model client. It consumes an initial model
reply and yields plain-data events. The notebook's `Clerk._work` is one adapter;
celldega-app can provide another using its renderer and Python worker.

The POC scope is: explain the current view, inspect evidence, show a cited view, return
to the user's saved view, export and reopen. Reports, the saved-view schema and the
workflow can be reused separately. Batch annotation, Make-tier execution and video
remain outside this acceptance path.

## Engine protocol v1

`celldega.clerk.engine.PROTOCOL_VERSION` identifies the event protocol. Start with
`run_turn(answer, max_rounds=6)`. Resume a `pause` using its `actions` as
`pending_actions` in a new invocation. The engine suppresses repeated consecutive
actions and stops on missing/failed completion before gathering further evidence.

| Event `kind` | Host responsibility | Value sent back to the generator |
| --- | --- | --- |
| `answer` | Display/store `text` and cited `views` | `None` |
| `findings` | Store proposals separately from accepted scientist annotations | `None` |
| `error` | Display/store `text` | `None` |
| `pause` | Store `actions`; offer explicit continuation with a fresh budget | `None` |
| `apply` | Validate `actions`, execute supported API operations, await completion | `{changes: [...], reads: {...}}` or `{error: "..."}` |
| `observe` | Capture coordinated snapshots, run requested reads, preserve evidence | A host-defined plain-data evidence envelope |
| `follow_up` | Send that evidence to the chosen model backend | Next reply string |

An asynchronous application adapter can drive the synchronous generator without
blocking its transport:

```python
from celldega.clerk import run_turn

workflow = run_turn(initial_reply)
response = None
while True:
    try:
        event = workflow.send(response)
    except StopIteration:
        break
    response = None
    if event["kind"] in {"apply", "observe", "follow_up"}:
        response = await host.resolve(event)
    else:
        await host.publish(event)
```

`host` is supplied by the embedding application. It owns model/session lifetime,
validation of allowed operations, widget addressing, cancellation, lookups, UI and
durable storage. The engine owns interpretation of action/view blocks, round budgets,
duplicate suppression and the decision to continue. This keeps provider-specific
sessions out of the visualization API.

## celldega-app integration points

The current sibling app has an Electron main-process `obs_app`, scoped window IDs,
renderer-held visualization instances and a persistent Python worker using JSON lines.
Use those boundaries rather than embedding notebook widgets:

1. Update the pinned JS dependency and managed Python lock together to a release
   containing these APIs. The inspected app currently pins Celldega 0.24.2 and uses
   older low-level rendering entry points; this branch is not a drop-in app update.
2. Keep each live visualization in the renderer's registry, addressed by `window_id`.
   Main routes requests carrying `request_id`, `window_id` and `scope_id`; validate the
   current scope for every request because a window can change datasets.
3. Dispatch only supported operations to `get_state`, `apply_state`, `snapshot` and
   `restore_snapshot`. Return completion/errors with the same request ID. Save/export
   remains a JS feature and should not require installing the Python runtime.
4. For Clerk, keep a workflow in the existing Python worker. Route its `apply` and
   `observe` requests to the renderer through main; route `follow_up` to the selected
   model backend. Keep images out of the globally broadcast `obs_app` channels.
5. Bind a proposed action to the evidence's data identity. For example, use
   `restore_snapshot({...evidenceSnapshot, state: proposedChanges})` to validate the
   dataset before applying the proposed settings. Capture the resulting view again;
   do not save the old evidence image as if it showed the new settings.
6. Persist saved-view envelopes and evidence records, not live widget/model objects.
   Reopening first loads the dataset, constructs fresh visualizations and invokes
   `restore_snapshot`. A scope ID routes linked windows; the content fingerprint
   validates their data. These are distinct responsibilities.

The standalone JS example exercises the renderer boundary without Electron. Engine
unit tests exercise a host without widgets or model credentials. An app integration
should additionally test window closure, cancellation, dataset switching during an
action, and responses arriving after a view is replaced. No celldega-app files are
changed by this branch.
