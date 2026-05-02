"""
push.py — One-shot GitHub push for the Pixel Verification bot.

DEFAULT BEHAVIOUR (destructive but always works):
    * rm -rf .git
    * git init
    * git add . && git commit -m <msg>
    * git branch -M <branch>
    * git remote add origin <GITHUB_REMOTE>
    * git push -u origin <branch> --force

Local commit history is wiped before each push and the remote branch is
overwritten. Use this when you only care about the latest snapshot of the
code and want push to never be rejected due to divergence.

Usage:
    python push.py "commit message"
    python push.py                       # default msg = "Update - YYYY-MM-DD HH:MM"
    python push.py "msg" --safe          # incremental push (no wipe), may fail
                                         #   if remote is ahead. Falls back to
                                         #   --force-with-lease when --force is also passed.
    python push.py "msg" --safe --force  # safe path + --force-with-lease

Environment variables:
    GITHUB_REMOTE     Remote URL, e.g. https://github.com/user/repo.git
                      (falls back to existing `origin` remote if set)
    GITHUB_BRANCH     Target branch (default: main)
    GITHUB_TOKEN      Optional. If GITHUB_REMOTE is https://, the token is
                      injected as basic auth (x-access-token:<token>@github.com).
    GIT_AUTHOR_NAME   Default: "Pixel Bot"
    GIT_AUTHOR_EMAIL  Default: "bot@pixel.local"
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
CYAN = "\033[96m"; BOLD = "\033[1m"; RESET = "\033[0m"


def log(msg: str, color: str = RESET) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{color}[{ts}] {msg}{RESET}")


def _load_dotenv() -> None:
    if not ENV_FILE.exists():
        return
    override_keys = {
        "GITHUB_TOKEN",
        "GITHUB_REMOTE",
        "GITHUB_BRANCH",
        "GITHUB_USER",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
    }
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and (k in override_keys or k not in os.environ):
            os.environ[k] = v


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True)
    if result.stdout.strip():
        print(f"  {result.stdout.strip()}")
    if result.stderr.strip():
        print(f"  {YELLOW}{result.stderr.strip()}{RESET}")
    if check and result.returncode != 0:
        raise RuntimeError("git command failed: " + " ".join(cmd))
    return result


def _inject_token(remote: str) -> str:
    token = env("GITHUB_TOKEN")
    if not token or not remote.startswith("https://"):
        return remote
    # Don't double-inject if userinfo already present
    after_scheme = remote.split("https://", 1)[1]
    host_part = after_scheme.split("/", 1)[0]
    if "@" in host_part:
        return remote
    user = env("GITHUB_USER", "x-access-token")
    return remote.replace("https://", f"https://{user}:{token}@", 1)


def resolve_remote() -> str | None:
    remote = env("GITHUB_REMOTE")
    if not remote:
        existing = run(["git", "remote", "get-url", "origin"])
        if existing.returncode == 0 and existing.stdout.strip():
            remote = existing.stdout.strip()
    if not remote:
        return None
    return _inject_token(remote)


def ensure_identity() -> None:
    name = env("GIT_AUTHOR_NAME", "Pixel Bot")
    email = env("GIT_AUTHOR_EMAIL", "bot@pixel.local")
    run(["git", "config", "user.name", name])
    run(["git", "config", "user.email", email])


def reset_push(commit_msg: str, branch: str) -> int:
    """Default mode: wipe .git, fresh init, force-push.
    Always succeeds (assuming auth is good and remote is reachable).
    Local commit history is reset on every run; remote branch is overwritten.
    """
    remote = resolve_remote()
    if not remote:
        log("GITHUB_REMOTE not set and no `origin` remote configured.", RED)
        log("  e.g.  export GITHUB_REMOTE=https://github.com/user/repo.git", YELLOW)
        return 1
    display_remote = env("GITHUB_REMOTE") or remote

    git_dir = ROOT / ".git"
    if git_dir.exists():
        log("Removing .git ...", YELLOW)
        shutil.rmtree(git_dir, ignore_errors=True)

    if run(["git", "init"]).returncode != 0:
        return 1
    ensure_identity()
    if run(["git", "add", "-A"]).returncode != 0:
        log("git add failed.", RED)
        return 1
    commit_res = run(["git", "commit", "-m", commit_msg])
    if commit_res.returncode != 0:
        log("git commit failed (nothing to commit?).", RED)
        return 1
    run(["git", "branch", "-M", branch])
    run(["git", "remote", "add", "origin", display_remote])
    log(f"Force-pushing to origin/{branch} ...", CYAN)
    return run(["git", "push", remote, f"HEAD:refs/heads/{branch}", "--force"]).returncode


def safe_push(commit_msg: str, branch: str, force: bool) -> int:
    """Incremental push that preserves local .git history.
    Will be rejected by the remote if the branch has diverged, unless
    `force=True` (which adds --force-with-lease).
    """
    git_dir = ROOT / ".git"
    if not git_dir.exists():
        log("No .git dir — initialising fresh repo (history starts here).", YELLOW)
        if run(["git", "init"]).returncode != 0:
            return 1

    ensure_identity()

    remote = resolve_remote()
    if not remote:
        log("GITHUB_REMOTE not set and no `origin` remote configured.", RED)
        log("  e.g.  export GITHUB_REMOTE=https://github.com/user/repo.git", YELLOW)
        return 1
    display_remote = env("GITHUB_REMOTE") or remote

    cur = run(["git", "remote", "get-url", "origin"])
    if cur.returncode != 0:
        run(["git", "remote", "add", "origin", display_remote])
    elif cur.stdout.strip() != display_remote:
        run(["git", "remote", "set-url", "origin", display_remote])

    run(["git", "add", "-A"], check=True)

    staged = run(["git", "diff", "--cached", "--name-only"])
    if not staged.stdout.strip():
        log("Nothing to commit — working tree matches HEAD.", YELLOW)
    else:
        log(f"Commit: {commit_msg}", CYAN)
        commit_res = run(["git", "commit", "-m", commit_msg])
        if commit_res.returncode != 0 and "nothing to commit" not in (commit_res.stdout + commit_res.stderr).lower():
            log("git commit failed.", RED)
            return 1

    push_cmd = ["git", "push"]
    if force:
        push_cmd.append("--force-with-lease")
    push_cmd.extend([remote, f"HEAD:refs/heads/{branch}"])

    log(f"Pushing to origin/{branch}{' (force-with-lease)' if force else ''}...", CYAN)
    return run(push_cmd).returncode


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GitHub push for Pixel Verification bot. Default = reset + force-push."
    )
    p.add_argument("commit_message", nargs="?", default="", help="Commit message")
    p.add_argument("--branch", default="", help="Target branch (default: GITHUB_BRANCH or 'main')")
    p.add_argument("--safe", action="store_true",
                   help="Incremental push (preserve .git history). May fail if remote diverged.")
    p.add_argument("--force", action="store_true",
                   help="Only with --safe: also pass --force-with-lease.")
    return p.parse_args()


def main() -> None:
    _load_dotenv()
    args = parse_args()
    commit_msg = args.commit_message or f"Update - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
    branch = args.branch or env("GITHUB_BRANCH", "main")

    mode_label = "safe (incremental)" if args.safe else "reset + force (default)"

    print(f"\n{BOLD}{GREEN}+================================+")
    print( "    GITHUB PUSH                   ")
    print( "+================================+" + RESET)
    print(f"{CYAN}Mode  : {mode_label}{RESET}")
    print(f"{CYAN}Branch: {branch}{RESET}")
    print(f"{CYAN}Msg   : {commit_msg!r}{RESET}\n")

    if args.safe:
        code = safe_push(commit_msg, branch, args.force)
    else:
        code = reset_push(commit_msg, branch)

    print(f"\n{BOLD}{CYAN}--------------------------------{RESET}")
    if code == 0:
        print(f"  {GREEN}✅ GitHub push successful!{RESET}\n")
    else:
        print(f"  {RED}❌ GitHub push failed (exit {code}).{RESET}\n")
        sys.exit(code)


if __name__ == "__main__":
    main()
