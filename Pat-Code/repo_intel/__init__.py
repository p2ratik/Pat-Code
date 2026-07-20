def __getattr__(name: str):
    if name == "RepoIntelligence":
        from repo_intel.intelligence import RepoIntelligence
        return RepoIntelligence
    raise AttributeError(f"module 'repo_intel' has no attribute {name!r}")

__all__ = ["RepoIntelligence"]
