"""``CaseFile`` -- durable, JSON-serializable annotation state for Clerk.

Clerk doesn't hand down verdicts; it assembles evidence and *makes a case* for a label
that the scientist rules on. A :class:`CaseFile` is the record of that case for a single
biological entity: the gathered evidence, Clerk's proposed label, the Q&A transcript, and
the human's accept/edit history.

The name mirrors ``CelldegaCollection`` / ``DegaFile``.

Design choice -- **key off the entity id, not the chat session.** Each CaseFile is
attached to a cluster / biological entity (e.g. leiden ``"5"``), so the evidence and the
ruling survive re-clustering, merges, and reloads. It is durable state, not chat
scrollback.

Design choice -- **a CaseFile is a human-readable store of results and decisions, not a
dump of AI/model state.** It records the evidence, the reasoning as readable prose, and
the human's ruling -- the curated scientific artifact an expert reviews and cites. It
deliberately does *not* store Claude/model internal state (session ids, raw
``stream-json``, token-level scratchpad, conversation-resume blobs). Resuming a *Claude*
conversation, if ever needed, is a separate ephemeral concern. This keeps CaseFiles
durable and reviewable even as the model/backend changes underneath.

Example::

    import celldega as dega

    cf = dega.clerk.CaseFile(entity_id="5", entity_attr="leiden")
    cf.gene_list = ["CD3D", "CD8A", "CD2"]
    cf.add_message("user", "What cell type is this?")
    cf.add_message("clerk", "Likely CD8+ T cells ...")
    cf.propose("CD8+ T cell")
    cf.accept()               # human rules
    cf.save("casefile_5.json")

    later = dega.clerk.CaseFile.load("casefile_5.json")
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json


@dataclass
class CaseFile:
    """Per-entity annotation record (see module docstring).

    Args:
        entity_id: The biological entity this record is attached to (e.g. a cluster id
            like ``"5"``). This is the key that makes the state durable.
        entity_attr: What ``entity_id`` refers to (e.g. ``"leiden"``, ``"cell_type"``).
        gene_list: Marker / DE genes used as evidence.
        context: Free-text context (dataset, notes).
        image_b64: Base64 PNG raster evidence (kept in memory; serialized inline).
        enrichr_terms: Pre-fetched Enrichr terms used as evidence.
        provenance: JSON-ready provenance for re-hydrating views -- e.g. a
            ``dega.select`` selection payload for a Yearbook, a Landscape ``view_state``,
            dataset name, segmentation. Free-form dict.
        messages: The Q&A transcript ``[{"role": ..., "content": ...}, ...]``.
        proposed_label: The label Clerk currently makes the case for.
        final_label: The label the human ruled on (empty until accepted/edited).
        status: ``"open"`` | ``"accepted"`` | ``"edited"``.
        history: Ruling events, e.g. ``[{"action": "accept", "label": "..."}]``.
    """

    entity_id: str
    entity_attr: str = "leiden"
    # raw data / provenance -- what the case was built from
    dataset: str = ""
    provenance: dict = field(default_factory=dict)
    assumptions: list = field(default_factory=list)
    # evidence
    gene_list: list = field(default_factory=list)
    enrichr_terms: list = field(default_factory=list)
    image_b64: str = ""
    context: str = ""
    # reasoning
    messages: list = field(default_factory=list)
    # conclusions
    proposed_label: str = ""
    final_label: str = ""
    status: str = "open"
    history: list = field(default_factory=list)

    # ---- transcript / evidence -------------------------------------------
    def add_message(self, role: str, content: str) -> "CaseFile":
        """Append a message to the transcript. Returns self for chaining."""
        self.messages.append({"role": role, "content": content})
        return self

    # ---- rulings ----------------------------------------------------------
    def propose(self, label: str) -> "CaseFile":
        """Record the label Clerk is making the case for (no human ruling yet)."""
        self.proposed_label = label
        self.history.append({"action": "propose", "label": label})
        return self

    def accept(self, label: str | None = None) -> "CaseFile":
        """The human accepts the proposed label (or an override)."""
        self.final_label = label if label is not None else self.proposed_label
        self.status = "accepted"
        self.history.append({"action": "accept", "label": self.final_label})
        return self

    def edit(self, label: str) -> "CaseFile":
        """The human overrides with a corrected label."""
        self.final_label = label
        self.status = "edited"
        self.history.append({"action": "edit", "label": label})
        return self

    @property
    def label(self) -> str:
        """The human's ruling if any, else Clerk's current proposal."""
        return self.final_label or self.proposed_label

    # ---- (de)serialization ------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_attr": self.entity_attr,
            "dataset": self.dataset,
            "provenance": dict(self.provenance),
            "assumptions": list(self.assumptions),
            "gene_list": list(self.gene_list),
            "enrichr_terms": list(self.enrichr_terms),
            "image_b64": self.image_b64,
            "context": self.context,
            "messages": list(self.messages),
            "proposed_label": self.proposed_label,
            "final_label": self.final_label,
            "status": self.status,
            "history": list(self.history),
        }

    def to_json(self, **kwargs) -> str:
        kwargs.setdefault("indent", 2)
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_dict(cls, data: dict) -> "CaseFile":
        data = dict(data)
        if "entity_id" not in data:
            raise ValueError("CaseFile requires an 'entity_id'.")
        # Only keep known fields so unknown/future keys don't break construction.
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def from_json(cls, text: str) -> "CaseFile":
        return cls.from_dict(json.loads(text))

    def save(self, path) -> None:
        """Write the CaseFile to a JSON file."""
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    @classmethod
    def load(cls, path) -> "CaseFile":
        """Read a CaseFile back from a JSON file."""
        with open(path, encoding="utf-8") as fh:
            return cls.from_json(fh.read())
