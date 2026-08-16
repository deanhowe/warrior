"""Shared forge plumbing for Warrior.

Everything the `warrior-*` tools need to talk to a git server safely, with no
machine-specific values compiled in. Three things live here:

1. Configuration     - env vars first, then ~/.warrior/config.json, then a
                       clear error naming exactly what to set. Never a guess.
2. Credentials       - OS keychain or environment variable ONLY. Never a file,
                       never a URL, never printed.
3. A safe Git surface - an allowlist of subcommands plus verb guards, so no
                       code path can force-push, reset, clean, prune or delete.

Hard-won rules encoded here (each cost something real to learn)
---------------------------------------------------------------
* `git status` rewrites `.git/index` and can execute repo-supplied hooks, so
  every invocation carries `--no-optional-locks -c core.fsmonitor=`.
* `git remote -v remove <name>` DELETES a remote. A guard that inspects
  `args[1]` is fooled by the `-v`; the verb check must run on the first
  NON-OPTION token. Verified against git 2.50.1.
* `git push <remote> :branch` deletes a remote branch, so no push argument may
  contain a colon.
* A filesystem path cannot push into Gitea (pre-receive rejects it) and a
  filesystem push into an already-up-to-date repo EXITS 0 HAVING SENT NOTHING.
  Transport is validated as SSH, and success is proven by finding the local
  HEAD among the server's refs - never by exit code 0.
* A mistyped `--output` once overwrote a repository's `.git/HEAD`. Output paths
  are validated before anything is written.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "ConfigError", "TransportError", "UnsafeGitCommand",
    "Settings", "SETTINGS", "default_config_path",
    "forge_token", "redact_url_userinfo", "sanitise_output",
    "sanitise_repo_name", "repo_name_for", "flatten_path", "join_ssh_url",
    "validate_ssh_transport", "is_ssh_transport",
    "assert_safe_git", "git", "parse_ls_remote", "head_landed",
    "safe_output_path", "is_token_transport_safe", "api",
]


class ConfigError(RuntimeError):
    """Configuration is missing, malformed, or unsafe. Always actionable."""


class TransportError(RuntimeError):
    """A remote URL is not a transport we are willing to push over."""


class UnsafeGitCommand(RuntimeError):
    """A git invocation was rejected before it could run."""


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

# Strips userinfo out of any URL so
# Git inspection can never print embedded credentials.
URL_USERINFO = re.compile(r"([a-z][a-z0-9+.-]*://)[^/@\s]+@", re.IGNORECASE)

# A URL carrying user:password. Legitimate config (ssh://git@host) has userinfo
# but no colon, so this catches credentials without rejecting normal remotes.
CREDENTIALED_URL = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s@]*:[^/\s@]*@", re.IGNORECASE)


def redact_url_userinfo(text: str) -> str:
    """Remove URL userinfo so inspection cannot print embedded credentials."""
    if not text:
        return text
    return URL_USERINFO.sub(r"\1[REDACTED]@", text)


def sanitise_output(text: str, *secrets: str | None) -> str:
    """Redact URL userinfo and blank out any literal secret before printing."""
    cleaned = redact_url_userinfo(text or "")
    for secret in secrets:
        # Short values would turn ordinary output into confetti.
        if secret and len(secret) >= 8:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# name -> (environment variable or None, what it is for)
SETTINGS: dict[str, tuple[str | None, str]] = {
    "git_ssh": ("WARRIOR_GIT_SSH",
                "SSH base URL of the git server, e.g. ssh://git@git.example.internal:2222"),
    "git_api": ("WARRIOR_GIT_API",
                "base URL of the forge API, e.g. https://git.example.internal/api/v1"),
    "git_owner": ("WARRIOR_GIT_OWNER",
                  "owner/namespace on the git server that repositories belong to"),
    "bare_root": ("WARRIOR_GIT_BARE_ROOT",
                  "directory holding the server's bare repositories, when it is on this machine"),
    "scan_root": ("WARRIOR_SCAN_ROOT",
                  "directory to scan for repositories, and the root that repo names flatten against"),
    "remote_name": ("WARRIOR_REMOTE_NAME",
                    "name to give the git remote that points at the server"),
    "keychain_service": ("WARRIOR_KEYCHAIN_SERVICE",
                         "OS keychain service name holding the forge API token"),
    "keychain_account": ("WARRIOR_KEYCHAIN_ACCOUNT",
                         "OS keychain account name holding the forge API token"),
    "gitea_db": ("WARRIOR_GITEA_DB",
                 "path to a local Gitea gitea.db, read strictly read-only"),
    "identity_db": ("WARRIOR_IDENTITY_DB",
                    "optional sqlite database of project identity/status metadata"),
    "identity_query": (None,
                       "SQL returning (path, status) rows from identity_db"),
    "identity_map": ("WARRIOR_IDENTITY_MAP",
                     "optional JSON file mapping repository name or path -> status"),
    "own_remotes": ("WARRIOR_OWN_REMOTES",
                    "regexes matching remotes you own, so your own mirrors are not called third-party"),
    "regions": (None, "classification rules: name prefix -> region and purpose"),
    "identity_overrides": (None, "classification rules: identity status -> purpose"),
    "known_purpose": (None, "classification rules: explicit per-repository judgements"),
}

# Settings that may carry a default because getting them wrong cannot lose work
# or send data anywhere. Everything else must be configured explicitly.
SAFE_DEFAULTS = {
    "remote_name": "warrior",
    "keychain_service": "warrior-git-token",
}

SECRET_KEY = re.compile(r"(token|password|passwd|secret|credential|api[_-]?key)", re.IGNORECASE)


def default_config_path() -> Path:
    override = os.environ.get("WARRIOR_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".warrior" / "config.json"


def _assert_no_secrets(data: Any, source: Path, trail: str = "") -> None:
    """Refuse to load a config file that contains credentials.

    Credentials come from the OS keychain or an environment variable. A token
    in a JSON file gets committed, backed up, and shared; a token inside a URL
    gets printed by every tool that echoes a remote.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            here = f"{trail}.{key}" if trail else str(key)
            if SECRET_KEY.search(str(key)):
                raise ConfigError(
                    f"{source}: key '{here}' looks like a credential.\n"
                    "  Warrior never reads secrets from a file.\n"
                    "  Put the token in the OS keychain, or in $WARRIOR_GIT_TOKEN, "
                    "and delete it from this file."
                )
            _assert_no_secrets(value, source, here)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            _assert_no_secrets(value, source, f"{trail}[{index}]")
    elif isinstance(data, str):
        if CREDENTIALED_URL.search(data):
            raise ConfigError(
                f"{source}: value at '{trail}' embeds credentials in a URL.\n"
                "  Warrior never accepts a credential inside a URL. Remove the "
                "user:password@ portion; authentication comes from the keychain "
                "or $WARRIOR_GIT_TOKEN."
            )


class Settings:
    """Resolved configuration: environment first, file second, error third."""

    def __init__(self, data: dict[str, Any] | None = None,
                 source: Path | None = None,
                 environ: dict[str, str] | None = None) -> None:
        self.data = data or {}
        self.source = source
        self.environ = os.environ if environ is None else environ

    @classmethod
    def load(cls, path: Path | None = None,
             environ: dict[str, str] | None = None) -> "Settings":
        config_path = Path(path).expanduser() if path else default_config_path()
        if not config_path.exists():
            return cls({}, config_path, environ)
        try:
            raw = json.loads(config_path.read_text())
        except (OSError, ValueError) as error:
            raise ConfigError(f"cannot read {config_path}: {error}") from None
        if not isinstance(raw, dict):
            raise ConfigError(f"{config_path}: top level must be a JSON object")
        _assert_no_secrets(raw, config_path)
        return cls(raw, config_path, environ)

    def resolve(self, name: str) -> tuple[Any, str]:
        """Return (value, source) where source is 'env', 'file', 'default' or 'unset'."""
        if name not in SETTINGS:
            raise KeyError(f"unknown setting {name!r}")
        env_name = SETTINGS[name][0]
        if env_name:
            value = self.environ.get(env_name)
            if value not in (None, ""):
                return self._coerce(name, value), "env"
        if name in self.data and self.data[name] not in (None, ""):
            return self.data[name], "file"
        if name in SAFE_DEFAULTS:
            return SAFE_DEFAULTS[name], "default"
        return None, "unset"

    @staticmethod
    def _coerce(name: str, value: str) -> Any:
        # Only list-valued settings need coercion out of a flat env var.
        if name == "own_remotes":
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    def get(self, name: str, default: Any = None) -> Any:
        value, source = self.resolve(name)
        return default if source == "unset" else value

    def require(self, name: str, why: str) -> Any:
        value, source = self.resolve(name)
        if source != "unset":
            return value
        env_name, description = SETTINGS[name]
        lines = [f"'{name}' is not configured ({description})."]
        lines.append(f"  It is needed to: {why}")
        if env_name:
            lines.append(f"  Set it with:   export {env_name}='<value>'")
        lines.append(f"  Or add to {self.source or default_config_path()}:")
        lines.append(f'                 {{ "{name}": <value> }}')
        raise ConfigError("\n".join(lines))

    def describe(self) -> list[tuple[str, str, str]]:
        """(name, displayable value, source) for every setting. Never a token."""
        rows = []
        for name in SETTINGS:
            value, source = self.resolve(name)
            if source == "unset":
                shown = "(unset)"
            elif isinstance(value, (dict, list)):
                shown = f"({len(value)} entries)"
            else:
                shown = redact_url_userinfo(str(value))
            rows.append((name, shown, source))
        return rows


# ---------------------------------------------------------------------------
# Credentials - keychain or environment, never a file, never printed
# ---------------------------------------------------------------------------

TOKEN_ENV = "WARRIOR_GIT_TOKEN"


def _macos_keychain(service: str, account: str) -> str | None:
    if not shutil.which("security"):
        return None
    command = ["security", "find-generic-password", "-s", service, "-w"]
    if account:
        command[2:2] = ["-a", account]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                check=False, stdin=subprocess.DEVNULL, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


def _secret_tool(service: str, account: str) -> str | None:
    if not shutil.which("secret-tool"):
        return None
    command = ["secret-tool", "lookup", "service", service]
    if account:
        command += ["account", account]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                check=False, stdin=subprocess.DEVNULL, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


def forge_token(settings: Settings, required: bool = True) -> str | None:
    """Fetch the forge API token. Returns the value; never logs or stores it."""
    value = settings.environ.get(TOKEN_ENV)
    if value:
        return value.strip()

    service = settings.get("keychain_service") or SAFE_DEFAULTS["keychain_service"]
    account = settings.get("keychain_account") or ""
    for reader in (_macos_keychain, _secret_tool):
        token = reader(service, account)
        if token:
            return token

    if not required:
        return None
    raise ConfigError(
        "no forge API token available.\n"
        f"  Warrior reads a token from ${TOKEN_ENV}, or from the OS keychain\n"
        f"  (service '{service}'"
        + (f", account '{account}'" if account else ", no account set")
        + ").\n"
        "  macOS:  security add-generic-password -s "
        f"'{service}'" + (f" -a '{account}'" if account else "") + " -w\n"
        "  Linux:  secret-tool store --label='warrior' service "
        f"'{service}'" + (f" account '{account}'" if account else "") + "\n"
        "  Warrior never reads a token from a file or from a URL."
    )


# ---------------------------------------------------------------------------
# Repository naming (Gitea AlphaDashDot)
# ---------------------------------------------------------------------------

# Gitea validates repository names as AlphaDashDot: ASCII letters, digits,
# '.', '-' and '_' only. Real paths broke that twice on the source machine - a
# '_~less' directory (illegal '~') and a scan root that flattens to the
# reserved name '-'. Both are sanitised rather than failing at the API.
RESERVED_NAMES = {"", ".", "..", "-", "_"}
MAX_NAME_LENGTH = 100


def sanitise_repo_name(name: str) -> str:
    """Coerce any string into a name a Gitea forge will accept."""
    cleaned = "".join(
        character if (character.isascii() and character.isalnum()) or character in "._-"
        else "-"
        for character in (name or "")
    )
    cleaned = cleaned.strip("-.")[:MAX_NAME_LENGTH].strip("-.")
    if cleaned in RESERVED_NAMES:
        return "repository"
    return cleaned


def flatten_path(path: str | Path, root: str | Path | None) -> str:
    """Flatten a path under `root` into a single name: case preserved, '/' and
    '.' collapsed to '-'. Returns '' when the path is not under root.

    Case is preserved on purpose (changed 2026-08-16) to match the naming
    convention already live in production - 234 real repositories created by
    an earlier process keep original case (e.g. `...-MeiliSearch`, not
    `...-meilisearch`). Lowercasing here would make every future repo this
    tool creates inconsistent with everything that already exists.
    """
    if root is None:
        return ""
    try:
        relative = Path(path).relative_to(Path(root))
    except ValueError:
        return ""
    return str(relative).replace("/", "-").replace(".", "-")


def repo_name_for(repo: str | Path, root: str | Path | None = None) -> str:
    """Name a repository on the server, flattening its path under `root`.

    Keeps names stable and collision-resistant: ~/code/apps/web and
    ~/code/tools/web become apps-web and tools-web, not two repos called web.
    """
    resolved = Path(repo).expanduser().resolve()
    flattened = ""
    if root is not None:
        try:
            resolved_root = Path(root).expanduser().resolve()
        except OSError:
            resolved_root = None
        if resolved_root is not None:
            flattened = flatten_path(resolved, resolved_root)
    if not flattened or flattened in RESERVED_NAMES:
        flattened = resolved.name.replace(".", "-")
    name = sanitise_repo_name(flattened)
    if name == "repository":
        name = sanitise_repo_name(resolved.name.replace(".", "-"))
    return name


def join_ssh_url(base: str, owner: str, name: str) -> str:
    """Join an SSH base with owner/name, tolerating both URL and scp-like bases."""
    base = (base or "").strip()
    if not base:
        raise ConfigError("empty SSH base URL")
    if base.endswith(":"):          # scp-like: git@host:
        return f"{base}{owner}/{name}.git"
    return f"{base.rstrip('/')}/{owner}/{name}.git"


# ---------------------------------------------------------------------------
# Transport validation - SSH only, never a filesystem path
# ---------------------------------------------------------------------------

SSH_URL = re.compile(r"^ssh://(?:[^/@\s]+@)?[^/\s:]+(?::\d+)?/.+", re.IGNORECASE)
SCP_LIKE = re.compile(r"^[^/\s:@]+@[^/\s:@]+:(?!//).+")


def is_ssh_transport(url: str) -> bool:
    url = (url or "").strip()
    return bool(SSH_URL.match(url) or SCP_LIKE.match(url))


def validate_ssh_transport(url: str) -> str:
    """Refuse anything that is not SSH.

    A filesystem path is READ-ONLY against Gitea: ls-remote, clone and fetch
    all work, but a push is rejected by the pre-receive hook. Worse, a
    filesystem push into an ALREADY UP-TO-DATE repository exits 0 having sent
    nothing, so it looks like it worked. It only fails once there is something
    real to push - which is the moment you needed it.
    """
    candidate = (url or "").strip()
    if not candidate:
        raise TransportError("empty remote URL")
    if is_ssh_transport(candidate):
        return candidate
    scheme = candidate.split("://", 1)[0].lower() if "://" in candidate else "(path)"
    raise TransportError(
        f"refusing to push over {scheme}: {redact_url_userinfo(candidate)}\n"
        "  Warrior pushes over SSH only (ssh://user@host[:port]/owner/repo.git).\n"
        "  A filesystem path cannot push into Gitea - and a filesystem push into\n"
        "  an already-up-to-date repository exits 0 having sent nothing, so the\n"
        "  failure is invisible until the moment you needed it to work."
    )


# ---------------------------------------------------------------------------
# The safe Git surface
# ---------------------------------------------------------------------------

# Allowlist, not a denylist: anything not named here cannot be run at all.
ALLOWED_GIT = frozenset(
    "branch config for-each-ref ls-remote push remote rev-list rev-parse "
    "status symbolic-ref tag".split()
)

# Flags that mutate or destroy, on any subcommand.
FORBIDDEN_GIT_FLAGS = frozenset(
    "-f --force --force-with-lease --force-if-includes --delete -d -D "
    "--prune --mirror --hard --soft --unset --unset-all --remove-section".split()
)

# Verbs that must never follow an allowed subcommand. Checked on the first
# NON-OPTION token: `git remote -v remove <name>` really does delete a remote,
# and a guard reading args[1] is fooled by the `-v`.
ALLOWED_VERBS: dict[str, frozenset[str]] = {
    "remote": frozenset({"add", "get-url", "show"}),
    "config": frozenset(),          # options only, no verb
    "branch": frozenset(),
    "tag": frozenset(),
    "status": frozenset(),
    "push": frozenset(),            # remote name is handled separately
}

# Options that hand execution to something else.
EXECUTION_OPTIONS = ("--exec", "--receive-pack", "--upload-pack")


def assert_safe_git(args: Sequence[str]) -> None:
    """Reject any git invocation that could delete, rewrite or force anything.

    Raises UnsafeGitCommand. This runs before every subprocess call, so no code
    path in Warrior - present or future - can destroy work by accident.
    """
    if not args:
        raise UnsafeGitCommand("no git subcommand given")
    subcommand = args[0]
    if subcommand not in ALLOWED_GIT:
        raise UnsafeGitCommand(
            f"git '{subcommand}' is not on Warrior's allowlist "
            f"({', '.join(sorted(ALLOWED_GIT))})"
        )

    rest = list(args[1:])
    for argument in rest:
        if argument in FORBIDDEN_GIT_FLAGS:
            raise UnsafeGitCommand(f"git {subcommand}: refusing destructive flag {argument}")
        if argument.startswith(EXECUTION_OPTIONS):
            raise UnsafeGitCommand(f"git {subcommand}: refusing {argument} (hands off execution)")

    if subcommand == "push":
        for argument in rest:
            # `git push <remote> :branch` deletes a remote branch.
            if ":" in argument:
                raise UnsafeGitCommand(
                    f"git push: refusing refspec {argument!r}; a colon refspec can delete refs"
                )
        return

    if subcommand == "config":
        if not any(option in {"--get", "--get-all", "--get-regexp", "--list", "-l"}
                   for option in rest):
            raise UnsafeGitCommand("git config: read-only options only (--get/--get-all/--list)")

    allowed_verbs = ALLOWED_VERBS.get(subcommand)
    if allowed_verbs is None:
        return
    first_verb = next((token for token in rest if not token.startswith("-")), None)
    if first_verb is not None and first_verb not in allowed_verbs:
        raise UnsafeGitCommand(
            f"git {subcommand}: refusing verb '{first_verb}'"
            + (f" (allowed: {', '.join(sorted(allowed_verbs))})" if allowed_verbs else
               " (this subcommand takes read-only options only)")
        )


# `status` rewrites .git/index and can execute repo-supplied hooks unless the
# filesystem monitor is disabled; optional locks are refused outright.
GIT_GLOBAL = ("--no-optional-locks", "-c", "core.fsmonitor=", "-c", "protocol.ext.allow=never")


def git(repo: str | Path, *args: str, timeout: int = 300) -> tuple[int, str, str]:
    """Run a validated, non-interactive git command. Returns (code, out, err)."""
    assert_safe_git(args)
    environment = dict(os.environ)
    environment.setdefault("GIT_TERMINAL_PROMPT", "0")
    environment.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes")
    try:
        process = subprocess.run(
            ["git", *GIT_GLOBAL, "-C", str(repo), *args],
            capture_output=True, text=True, check=False,
            stdin=subprocess.DEVNULL, timeout=timeout, env=environment,
        )
    except subprocess.TimeoutExpired:
        return -1, "", f"timed out after {timeout}s"
    except OSError as error:
        return -1, "", str(error)
    return process.returncode, process.stdout.strip(), process.stderr.strip()


def parse_ls_remote(output: str) -> dict[str, str]:
    """Parse `git ls-remote` into {ref: sha}. Malformed lines are ignored."""
    refs: dict[str, str] = {}
    for line in (output or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-f]{7,64}", parts[0]):
            refs[parts[1]] = parts[0]
    return refs


def head_landed(ls_remote_output: str, local_head: str) -> bool:
    """Is the local HEAD actually on the server?

    Compares whole SHAs. A substring test ('sha in output') reports success
    when the server merely holds a LONGER sha that happens to start with the
    same characters, which is exactly the kind of false green this tool exists
    to prevent. Exit code 0 proves nothing: a push with nothing to send also
    exits 0.
    """
    head = (local_head or "").strip()
    if not head:
        return False
    return head in set(parse_ls_remote(ls_remote_output).values())


# ---------------------------------------------------------------------------
# Output paths - the mistyped --output that overwrote a .git/HEAD
# ---------------------------------------------------------------------------

GIT_INTERNAL_NAMES = frozenset(
    "HEAD ORIG_HEAD FETCH_HEAD MERGE_HEAD CHERRY_PICK_HEAD config index "
    "packed-refs description shallow COMMIT_EDITMSG".split()
)


def safe_output_path(path: str | Path, *, overwrite: bool = False,
                     suffixes: Iterable[str] = (".json",)) -> Path:
    """Validate a --output destination before a single byte is written.

    During this tool's own audit a mistyped --output overwrote a repository's
    .git/HEAD and broke it. Everything below is a direct consequence.
    """
    target = Path(path).expanduser()
    suffixes = tuple(suffixes)

    if any(part == ".git" or part.endswith(".git") for part in target.parts[:-1]):
        raise ConfigError(
            f"refusing to write inside a git directory: {target}\n"
            "  A mistyped --output once overwrote a repository's .git/HEAD."
        )
    if target.name in GIT_INTERNAL_NAMES:
        raise ConfigError(f"refusing to write to a git internal filename: {target.name}")
    if target.suffix not in suffixes:
        raise ConfigError(
            f"--output must end in {' or '.join(suffixes)} (got {target.name!r})"
        )
    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        raise ConfigError(f"output directory does not exist: {parent}")
    if target.is_symlink():
        raise ConfigError(f"refusing to write through a symlink: {target}")
    if target.exists():
        if not target.is_file():
            raise ConfigError(f"refusing to overwrite a non-file: {target}")
        if not overwrite:
            raise ConfigError(f"{target} already exists; pass --overwrite to replace it")
    return target


# ---------------------------------------------------------------------------
# Forge API
# ---------------------------------------------------------------------------

LOCAL_SUFFIXES = (".local", ".internal", ".test", ".lan", ".localhost", ".home.arpa")
INSECURE_OPT_IN = "WARRIOR_ALLOW_INSECURE_API"


def is_token_transport_safe(base_url: str) -> bool:
    """May we send an Authorization header to this URL?

    https always; http only to this machine or a private-scope hostname.
    """
    parts = urllib.parse.urlsplit((base_url or "").strip())
    if parts.scheme == "https":
        return True
    if parts.scheme != "http":
        return False
    host = (parts.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        return True
    return host.endswith(LOCAL_SUFFIXES)


def api(base_url: str, path: str, token: str, method: str = "GET",
        payload: dict[str, Any] | None = None, timeout: int = 20) -> tuple[int, Any]:
    """Call the forge API. Returns (status, parsed-body-or-text).

    Status -1 means the request never completed. The token is sent in a header,
    never in the URL, and never appears in a returned message.
    """
    if not is_token_transport_safe(base_url) and not os.environ.get(INSECURE_OPT_IN):
        raise ConfigError(
            f"refusing to send an API token over {redact_url_userinfo(base_url)}\n"
            "  Plain http to a non-local host would expose the token on the wire.\n"
            f"  Use https, or set {INSECURE_OPT_IN}=1 if this really is a trusted "
            "private network."
        )
    url = f"{base_url.rstrip('/')}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"token {token}")
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    elif method in {"PUT", "POST"}:
        request.add_header("Content-Length", "0")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode()
            try:
                return response.status, json.loads(body) if body else None
            except ValueError:
                return response.status, body[:400]
    except urllib.error.HTTPError as error:
        detail = ""
        try:
            detail = error.read().decode()[:200]
        except OSError:
            pass
        return error.code, sanitise_output(detail, token)
    except (urllib.error.URLError, OSError, ValueError) as error:
        return -1, sanitise_output(str(error), token)


def authenticated_login(base_url: str, token: str) -> str | None:
    status, body = api(base_url, "/user", token)
    if status == 200 and isinstance(body, dict):
        return str(body.get("login") or "") or None
    return None
