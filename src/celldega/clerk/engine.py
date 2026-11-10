"""Bounded Clerk workflow, independent of widgets, transports and model providers.

``run_turn`` is a generator of plain-data events. Hosts resolve ``apply``,
``observe`` and ``follow_up`` requests using ``send(result)``. Other events are
notifications and resume with ``send(None)``. This works with notebook comms,
an application's browser bridge, or a headless test adapter. No model or browser
side effect happens inside the engine.
"""

from __future__ import annotations

from copy import deepcopy
import json

from .llm import extract_actions, extract_findings, extract_views


PROTOCOL_VERSION = 1


def run_turn(
    answer: str | None = None, *, max_rounds: int = 6, pending_actions: dict | None = None
):
    """Interpret a reply, perform bounded evidence rounds, or emit resumable pause.

    ``apply`` returns ``{changes: [...], reads: {...}}`` only after completion, or
    ``{error: message}``. ``observe`` receives that result and returns host evidence;
    ``follow_up`` receives that evidence and returns the next model reply string.
    A pause carries actions which can start a new invocation via ``pending_actions``.
    """
    if isinstance(max_rounds, bool) or not isinstance(max_rounds, int) or max_rounds < 0:
        raise ValueError("max_rounds must be a nonnegative integer")
    rounds, previous = 0, None
    while True:
        if pending_actions is not None:
            actions, problem, pending_actions = pending_actions, None, None
        else:
            text, actions, problem = extract_actions(answer or "")
            text, findings, findings_problem = extract_findings(text)
            text, views, views_problem = extract_views(text)
            if text:
                yield {"kind": "answer", "text": text, "views": views or {}}
            if findings:
                yield {"kind": "findings", "findings": findings}
            for issue in (problem, findings_problem, views_problem):
                if issue:
                    yield {"kind": "error", "text": issue}
        if problem or not actions:
            return
        actions = deepcopy(actions)
        keep_going = bool(actions.pop("continue", False))
        signature = json.dumps(actions, sort_keys=True, default=str)
        if signature == previous:
            return
        if rounds >= max_rounds:
            yield {
                "kind": "pause",
                "rounds": rounds,
                "actions": {**actions, "continue": keep_going},
            }
            return
        previous = signature
        rounds += 1
        result = yield {"kind": "apply", "actions": actions}
        if (
            not isinstance(result, dict)
            or result.get("error")
            or not isinstance(result.get("changes"), list)
            or not isinstance(result.get("reads"), dict)
        ):
            error = result.get("error") if isinstance(result, dict) else None
            yield {
                "kind": "error",
                "text": "Couldn't do that: " + str(error or "missing action completion"),
            }
            return
        reads = result.get("reads") or {}
        has_reads = any(reads.get(key) for key in ("genes", "markers", "enrichr", "pubmed"))
        evidence = yield {
            "kind": "observe",
            "actions": actions,
            "changes": result.get("changes") or [],
            "reads": reads,
            "continue": has_reads or keep_going,
        }
        if not (has_reads or keep_going):
            return
        answer = yield {"kind": "follow_up", "evidence": evidence}
