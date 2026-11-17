import json

import pytest

from celldega.clerk.engine import run_turn


def answer(actions):
    return "Checking.\n```celldega-actions\n" + json.dumps(actions) + "\n```"


def test_headless_explain_inspect_show_cycle_has_no_widget_dependency():
    workflow = run_turn(answer({"landscape": {"clusters": ["4"]}, "continue": True}))
    assert next(workflow)["kind"] == "answer"
    action = workflow.send(None)
    assert action == {"kind": "apply", "actions": {"landscape": {"clusters": ["4"]}}}
    observed = workflow.send({"changes": ["cluster 4"], "reads": {"genes": []}})
    assert observed["kind"] == "observe" and observed["continue"]
    evidence = {"observations": {"cluster": "4"}, "snapshot": "portable-snapshot"}
    assert workflow.send(evidence) == {"kind": "follow_up", "evidence": evidence}
    assert workflow.send("The view supports the claim.")["kind"] == "answer"
    with pytest.raises(StopIteration):
        workflow.send(None)


@pytest.mark.parametrize("result", [None, {}, {"error": "browser timeout"}])
def test_failed_or_missing_completion_never_becomes_observed_evidence(result):
    workflow = run_turn(pending_actions={"landscape": {"clusters": ["4"]}})
    assert next(workflow)["kind"] == "apply"
    assert workflow.send(result)["kind"] == "error"
    with pytest.raises(StopIteration):
        workflow.send(None)


def test_pause_is_plain_data_and_can_resume_in_another_host():
    actions = {"landscape": {"clusters": ["4"]}}
    paused = next(run_turn(pending_actions=actions, max_rounds=0))
    assert paused["kind"] == "pause"
    reopened = json.loads(json.dumps(paused))
    resumed = run_turn(pending_actions=reopened["actions"], max_rounds=1)
    assert next(resumed)["kind"] == "apply"
    assert resumed.send({"changes": ["cluster 4"], "reads": {}})["kind"] == "observe"
    with pytest.raises(StopIteration):
        resumed.send({})
