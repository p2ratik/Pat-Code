"""
file_discovery.py — .gitignore-aware source file discovery for repo_intel.

Mandatory first pass before indexing: returns only source files that belong
to the repo (respecting .gitignore and a hard exclusion list), so build
artifacts and vendored code never enter the graph.
"""

from pathlib import Path
from typing import Iterator

import pathspec

from repo_intel.tag_extractor import _LANG_REGISTRY


_EXCLUDED_DIRS: frozenset[str] = frozenset({
    # Python
    "__pycache__", ".venv", "venv", ".env", "env",
    "*.egg-info", ".eggs",
    # JS/TS runtimes and package dirs
    "node_modules",
    # JS/TS framework build outputs
    ".next", ".nuxt", ".svelte-kit", ".turbo",
    # Generic build outputs
    "build", "dist", "out", "target", ".build",
    "coverage", ".coverage",
    # VCS / tooling
    ".git", ".svn", ".hg",
    ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".tox", ".nox",
    # IDE / OS
    ".idea", ".vscode", "__MACOSX",
    # Misc vendored / generated
    "vendor", "third_party", "thirdparty",
    ".conda", ".venv2",
})

# Known source file extensions — only these are returned
_SOURCE_EXTS: frozenset[str] = frozenset(_LANG_REGISTRY.keys())



def _load_gitignore(root: Path) -> pathspec.PathSpec:
    """Return a PathSpec compiled from root/.gitignore, or an empty spec."""
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return pathspec.PathSpec.from_lines("gitwildmatch", [])
    lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def _is_excluded_dir(name: str) -> bool:
    """True if a directory name matches the hard exclusion list."""
    import fnmatch
    return any(fnmatch.fnmatch(name, pattern) for pattern in _EXCLUDED_DIRS)


def _is_source_file(path: Path) -> bool:
    """True if the file has an extension we can parse."""
    return path.suffix.lower() in _SOURCE_EXTS


def _is_gitignored(rel_path: str, spec: pathspec.PathSpec) -> bool:
    """True if the relative path is matched by the gitignore spec."""
    return spec.match_file(rel_path)


def discover_files(root: str | Path) -> list[Path]:
    """
    Return absolute Paths of indexable source files under root.

    Excludes: hard-blocked dirs, .gitignore-matched paths, non-source extensions.
    """
    root = Path(root).resolve()
    spec = _load_gitignore(root)
    return list(_walk(root, root, spec))


def _walk(root: Path, current: Path, spec: pathspec.PathSpec) -> Iterator[Path]:
    """Recursively yield source files, pruning excluded and gitignored dirs."""
    try:
        entries = sorted(current.iterdir())
    except PermissionError:
        return

    for entry in entries:
        if entry.is_symlink():
            continue

        rel = entry.relative_to(root).as_posix()

        if entry.is_dir():
            if _is_excluded_dir(entry.name) or _is_gitignored(rel + "/", spec):
                continue
            yield from _walk(root, entry, spec)

        elif entry.is_file():
            if _is_source_file(entry) and not _is_gitignored(rel, spec):
                yield entry
