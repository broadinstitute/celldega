"""Build a storyboard's figure in one command: data -> captures -> composed PNG.

    uv run --no-project --with playwright --with pyyaml --with pillow \\
        python figures/tools/build_figure.py figures/storyboards/hcrc.yaml

Runs the storyboard's data step (``figures/tools/prepare_<id>.py``, in the dega
environment, when its outputs are missing or ``--prepare`` is given), then
capture.py (every panel, or ``--panels a1 c2``), then compose.py, and prints the
path of ``figures/build/<id>/figure.png``. ``--compose-only`` re-lays out the text
without recapturing.
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import subprocess
import sys

import yaml


TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))

from capture import capture  # noqa: E402
from compose import compose  # noqa: E402


def prepare(story: dict, force: bool) -> None:
    """The storyboard's data step, run with the dega environment's Python."""
    script = TOOLS / f"prepare_{story['id']}.py"
    facts = REPO / "figures/build" / story["id"] / "data/facts.json"
    if not script.exists() or (facts.exists() and not force):
        return
    python = REPO / "dega/bin/python"
    subprocess.run([str(python if python.exists() else sys.executable), str(script)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("--panels", nargs="*", help="capture only these panel ids")
    parser.add_argument("--prepare", action="store_true", help="rerun the data step")
    parser.add_argument("--compose-only", action="store_true", help="skip the captures")
    args = parser.parse_args()
    story = yaml.safe_load(args.storyboard.read_text())
    prepare(story, args.prepare)
    if not args.compose_only:
        asyncio.run(capture(args.storyboard, args.panels))
    print(compose(args.storyboard))


if __name__ == "__main__":
    main()
