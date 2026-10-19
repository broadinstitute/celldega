"""Push an existing DegaFiles Git repository in bounded, resumable batches."""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--expected-origin", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--max-files", type=int, default=1000)
    parser.add_argument("--max-mib", type=int, default=128)
    parser.add_argument(
        "--execute", action="store_true", help="Commit and push; otherwise only plan"
    )
    args = parser.parse_args()
    root = args.directory.resolve()
    if args.max_files < 1 or args.max_mib < 1:
        parser.error("Batch limits must be positive")

    def git(*arguments, check=True, capture=True):
        return subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "-c",
                "core.compression=1",
                "-c",
                "pack.window=0",
                "-c",
                "pack.threads=2",
                *arguments,
            ],
            check=check,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )

    if Path(git("rev-parse", "--show-toplevel").stdout.decode().strip()).resolve() != root:
        raise RuntimeError("The directory must be its own Git repository, not its parent's")
    if git("remote", "get-url", "origin").stdout.decode().strip() != args.expected_origin:
        raise RuntimeError("origin does not match the explicitly requested repository")
    if git("symbolic-ref", "--short", "HEAD").stdout.decode().strip() != args.branch:
        raise RuntimeError("The current branch does not match the requested branch")
    if git("diff", "--quiet", check=False).returncode:
        raise RuntimeError("Tracked files have changed; review them before resuming")
    if git("diff", "--cached", "--quiet", check=False).returncode:
        raise RuntimeError("The index contains staged changes; review them before resuming")

    paths = [
        p.decode()
        for p in git("ls-files", "--others", "--exclude-standard", "-z").stdout.split(b"\0")
        if p
    ]

    def section(path):
        parts = Path(path).parts
        return parts[0] if len(parts) > 1 else "metadata"

    order = {
        "metadata": 0,
        "cell_clusters": 1,
        "pyramid_images": 2,
        "cbg": 3,
        "cell_segmentation": 4,
        "transcript_tiles": 5,
    }
    paths.sort(key=lambda p: (order.get(section(p), 99), section(p), p))
    batches = []
    batch = []
    batch_bytes = 0
    batch_section = None
    for relative in paths:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Expected an ordinary file: {relative}")
        size = path.stat().st_size
        if size >= 100 * 1024**2 or size > args.max_mib * 1024**2:
            raise RuntimeError(f"File exceeds an upload limit: {relative}")
        scope = section(relative)
        if batch and (
            scope != batch_section
            or len(batch) >= args.max_files
            or batch_bytes + size > args.max_mib * 1024**2
        ):
            batches.append({"section": batch_section, "bytes": batch_bytes, "files": batch})
            batch, batch_bytes = [], 0
        batch_section = scope
        batch.append(relative)
        batch_bytes += size
    if batch:
        batches.append({"section": batch_section, "bytes": batch_bytes, "files": batch})
    print(
        f"Plan: {len(paths):,} files, {sum(b['bytes'] for b in batches) / 1024**3:.2f} GiB, {len(batches)} batches",
        flush=True,
    )
    print("Batches by section:", dict(Counter(b["section"] for b in batches)), flush=True)
    if not args.execute:
        return

    git_dir = root / ".git"
    (git_dir / "upload-plan.json").write_text(json.dumps(batches, indent=2) + "\n")
    ref = f"refs/heads/{args.branch}"
    remote = git("ls-remote", "origin", ref).stdout.decode().split()
    local = git("rev-parse", "--verify", "HEAD", check=False)
    last_push = 0.0

    def push():
        nonlocal last_push
        for attempt in range(3):
            time.sleep(max(0, 12 - (time.monotonic() - last_push)))
            last_push = time.monotonic()
            result = git("push", "--porcelain", "origin", f"HEAD:{ref}", capture=False, check=False)
            if result.returncode == 0:
                return
            if attempt < 2:
                print("Push failed; retrying the same commit in 20 seconds.", flush=True)
                time.sleep(20)
        raise RuntimeError("Push failed; rerun to retry this commit before adding another batch")

    if remote:
        git("fetch", "--quiet", "origin", f"{ref}:refs/remotes/origin/{args.branch}")
        if local.returncode != 0:
            raise RuntimeError("Remote is nonempty but this repository has no local history")
        if git("merge-base", "--is-ancestor", remote[0], "HEAD", check=False).returncode:
            raise RuntimeError(
                "Remote contains history not present locally; refusing to overwrite it"
            )
        pending = int(git("rev-list", "--count", f"{remote[0]}..HEAD").stdout)
        if pending > 1:
            raise RuntimeError("More than one unpushed commit; inspect history before resuming")
        if pending == 1:
            print("Resuming with the previously committed, unpushed batch.", flush=True)
            push()
    elif local.returncode == 0:
        if int(git("rev-list", "--count", "HEAD").stdout) != 1:
            raise RuntimeError("Nonempty local history and an empty remote; inspect before pushing")
        push()

    for i, batch in enumerate(batches, start=1):
        print(
            f"Batch {i}/{len(batches)}: {batch['section']}, {len(batch['files']):,} files, {batch['bytes'] / 1024**2:.1f} MiB",
            flush=True,
        )
        pathspec = git_dir / "upload-pathspec"
        pathspec.write_bytes(b"\0".join(p.encode() for p in batch["files"]) + b"\0")
        git("--literal-pathspecs", "add", f"--pathspec-from-file={pathspec}", "--pathspec-file-nul")
        message = f"Add {batch['section']} batch {i}/{len(batches)} ({len(batch['files'])} files)"
        git("commit", "--quiet", "-m", message)
        push()
        print("Pushed:", git("rev-parse", "--short", "HEAD").stdout.decode().strip(), flush=True)

    local_sha = git("rev-parse", "HEAD").stdout.decode().strip()
    remote_sha = git("ls-remote", "origin", ref).stdout.decode().split()[0]
    if local_sha != remote_sha:
        raise RuntimeError("Final remote commit does not match local HEAD")
    remaining = git("ls-files", "--others", "--exclude-standard", "-z").stdout
    if remaining or git("diff", "--quiet", check=False).returncode:
        raise RuntimeError("Files changed during upload; run another reviewed batch")
    tracked = len([p for p in git("ls-files", "-z").stdout.split(b"\0") if p])
    print(f"COMPLETE: {tracked:,} tracked files; remote {args.branch} = {local_sha}", flush=True)


if __name__ == "__main__":
    main()
