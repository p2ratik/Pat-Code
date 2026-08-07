"""
tag_extractor.py — tree-sitter tag and relation extraction for repo_intel.

Custom implementation using tree-sitter directly (no grep_ast).
Loads .scm query files, runs QueryCursor captures, and yields Tag namedtuples.
Runtime deps: tree-sitter >= 0.24, individual tree-sitter-<lang> packages.
"""

import logging
import sys as _sys
from collections import namedtuple
from pathlib import Path

from tree_sitter import Language, Parser, Query, QueryCursor


Tag = namedtuple("Tag", "rel_fname fname line end_line name kind")
"""
kind is one of: 'def' | 'ref' | 'import' | 'inherit'
line / end_line are 0-based row indices.
"""



_LANG_REGISTRY: dict[str, tuple[str, object]] = {}


def _register() -> None:
    """Populate _LANG_REGISTRY from whatever tree-sitter-X packages are installed."""
    import importlib

    _simple = [
        ("python", "tree_sitter_python", [".py"]),
        ("javascript", "tree_sitter_javascript", [".js", ".mjs", ".cjs"]),
        ("java", "tree_sitter_java", [".java"]),
        ("c", "tree_sitter_c", [".c", ".h"]),
        ("cpp", "tree_sitter_cpp", [".cpp", ".cc", ".cxx", ".hpp", ".hxx"]),
        ("rust", "tree_sitter_rust", [".rs"]),
        ("go", "tree_sitter_go", [".go"]),
        ("bash", "tree_sitter_bash", [".sh", ".bash"]),
        ("ruby", "tree_sitter_ruby", [".rb"]),
        ("c_sharp", "tree_sitter_c_sharp", [".cs"]),
        ("lua", "tree_sitter_lua", [".lua"]),
        ("scala", "tree_sitter_scala", [".scala"]),
        ("kotlin", "tree_sitter_kotlin", [".kt", ".kts"]),
        ("swift", "tree_sitter_swift", [".swift"]),
    ]
    for lang_name, mod_name, exts in _simple:
        try:
            mod = importlib.import_module(mod_name)
            if not hasattr(mod, "language"):
                continue
            for ext in exts:
                _LANG_REGISTRY[ext] = (lang_name, mod.language)
        except ImportError:
            pass

    try:
        import tree_sitter_typescript as tsts
        _LANG_REGISTRY[".ts"] = ("typescript", tsts.language_typescript)
        _LANG_REGISTRY[".tsx"] = ("tsx", tsts.language_tsx)
    except ImportError:
        pass

    # PHP similarly
    try:
        import tree_sitter_php as tsphp
        _LANG_REGISTRY[".php"] = ("php", tsphp.language_php)
    except ImportError:
        pass


_register()

if not _LANG_REGISTRY:
    logging.error(
        "repo_intel: _register() loaded 0 tree-sitter language parsers. "
        "Graph indexing will produce no results. If running as a packaged executable, "
        "ensure tree_sitter_python, tree_sitter_javascript etc. are in hiddenimports."
    )
else:
    logging.debug(
        "repo_intel: registered %d tree-sitter language(s): %s",
        len(_LANG_REGISTRY),
        ", ".join(sorted(set(name for name, _ in _LANG_REGISTRY.values()))),
    )

# Cache parsed Language objects so we don't reconstruct them per-file
_LANGUAGE_CACHE: dict[str, Language] = {}
_PARSER_CACHE: dict[str, Parser] = {}


def _get_language_and_parser(ext: str) -> tuple[Language, Parser] | None:
    """Return a cached (Language, Parser) pair for the given extension, or None."""
    if ext not in _LANG_REGISTRY:
        return None
    if ext in _LANGUAGE_CACHE:
        return _LANGUAGE_CACHE[ext], _PARSER_CACHE[ext]
    lang_name, factory = _LANG_REGISTRY[ext]
    language = Language(factory())
    parser = Parser(language)
    _LANGUAGE_CACHE[ext] = language
    _PARSER_CACHE[ext] = parser
    return language, parser


def _get_scm_base() -> Path:
    """Resolve the queries directory whether running frozen (PyInstaller) or from source."""
    if getattr(_sys, 'frozen', False):
        # PyInstaller extracts bundled data to sys._MEIPASS
        return Path(_sys._MEIPASS) / "queries" / "tree-sitter-language-pack"
    return Path(__file__).parent.parent / "queries" / "tree-sitter-language-pack"

_SCM_DIR = _get_scm_base()

if not _SCM_DIR.exists():
    logging.error(
        "repo_intel: tree-sitter query directory not found at '%s'. "
        "Code intelligence (search_entity / traverse_graph) will return no results. "
        "If running as a packaged executable, ensure .scm files are bundled in the spec.",
        _SCM_DIR,
    )

# Map internal language names that differ from their .scm filename prefix.
# e.g. _LANG_REGISTRY uses 'c_sharp' but the file is 'csharp-tags.scm'.
_SCM_LANG_NAME_MAP: dict[str, str] = {
    "c_sharp": "csharp",
}


def _load_scm(lang_name: str, suffix: str) -> str | None:
    """Read a .scm query file from the queries directory, return text or None."""
    file_lang = _SCM_LANG_NAME_MAP.get(lang_name, lang_name)
    path = _SCM_DIR / f"{file_lang}-{suffix}.scm"
    return path.read_text(encoding="utf-8") if path.exists() else None



def _run_captures(language: Language, scm_text: str, root_node) -> dict:
    """Compile a Query and run it via QueryCursor, returning {capture_name: [nodes]}."""
    query = Query(language, scm_text)
    cursor = QueryCursor(query)
    return cursor.captures(root_node)


def extract_tags(fname: str, rel_fname: str) -> list[Tag]:
    """Parse fname with tree-sitter and return Tags for defs, refs, imports, and inherits."""
    ext = Path(fname).suffix.lower()
    pair = _get_language_and_parser(ext)
    if pair is None:
        return []

    language, parser = pair
    lang_name = _LANG_REGISTRY[ext][0]

    tags_scm = _load_scm(lang_name, "tags")
    if tags_scm is None:
        logging.debug("No tags.scm for %s, skipping %s", lang_name, fname)
        return []

    try:
        code = Path(fname).read_bytes()
    except OSError as exc:
        logging.debug("Cannot read %s: %s", fname, exc)
        return []

    tree = parser.parse(code)
    root = tree.root_node

    results: list[Tag] = []


    tags_caps = _run_captures(language, tags_scm, root)
    for cap_name, nodes in tags_caps.items():
        if cap_name.startswith("name.definition."):
            kind = "def"
        elif cap_name.startswith("name.reference."):
            kind = "ref"
        else:
            continue
        for node in nodes:
            # Parent of the name identifier is the definition node (class_definition, function_definition, …)
            def_node = node.parent
            results.append(Tag(
                rel_fname=rel_fname,
                fname=fname,
                line=node.start_point[0],
                end_line=def_node.end_point[0] if def_node else node.start_point[0],
                name=node.text.decode("utf-8"),
                kind=kind,
            ))

    relations_scm = _load_scm(lang_name, "relations")
    if relations_scm:
        rel_caps = _run_captures(language, relations_scm, root)
        for cap_name, nodes in rel_caps.items():
            if cap_name.startswith("name.relation.import"):
                kind = "import"
            elif cap_name.startswith("name.relation.inherit"):
                kind = "inherit"
            else:
                continue
            for node in nodes:
                results.append(Tag(
                    rel_fname=rel_fname,
                    fname=fname,
                    line=node.start_point[0],
                    end_line=node.end_point[0],
                    name=node.text.decode("utf-8"),
                    kind=kind,
                ))

    return results
