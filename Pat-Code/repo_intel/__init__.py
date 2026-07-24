def __getattr__(name: str):
    if name == "RepoIntelligence":
        from repo_intel.intelligence import RepoIntelligence
        return RepoIntelligence
    if name == "render_traversal":
        from repo_intel.renderer import render_traversal
        return render_traversal
    raise AttributeError(f"module 'repo_intel' has no attribute {name!r}")

__all__ = ["RepoIntelligence", "render_traversal"]
