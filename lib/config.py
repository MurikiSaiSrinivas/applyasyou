"""Config loader for the generic starter kit.

All user-specific settings live in config.json (gitignored). Scripts call
load_config() and the small accessors below instead of hardcoding anything.

A script in generic/scripts/ uses this by adding the package root to sys.path:

    import os, sys
    PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, PKG_ROOT)
    from lib.config import load_config, prospects_dir, stack_keywords
"""
import json
import os


class ConfigError(Exception):
    pass


def pkg_root():
    """generic/ — the package root (lib/config.py -> lib -> generic)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config():
    """Load config.json from the package root. Raises ConfigError with a
    copy-paste fix if it's missing."""
    root = pkg_root()
    path = os.path.join(root, "config.json")
    if not os.path.exists(path):
        raise ConfigError(
            "config.json not found.\n"
            "Copy the example and edit it for yourself:\n"
            f"  copy config.example.json config.json   (Windows)\n"
            f"  cp config.example.json config.json      (Mac/Linux)\n"
            f"Expected at: {path}"
        )
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["_root"] = root
    return cfg


# ----- path accessors -----

def _rel(cfg, key, default):
    return os.path.join(cfg["_root"], cfg.get("paths", {}).get(key, default))


def data_dir(cfg):
    return _rel(cfg, "data_dir", "data")


def prospects_dir(cfg):
    return _rel(cfg, "prospects_dir", "data/prospects")


def resumes_dir(cfg):
    return _rel(cfg, "resumes_dir", "resumes")


# ----- content accessors (strip __notes keys) -----

def _strip_notes(d):
    return {k: v for k, v in (d or {}).items() if not str(k).startswith("__")}


def stack_keywords(cfg):
    """Return [(keyword, weight), ...] from config.stack_keywords."""
    return [(k, v) for k, v in _strip_notes(cfg.get("stack_keywords")).items()]


def resume_clusters(cfg):
    """Return {resume_path: [keywords]} from config.resume_clusters."""
    return _strip_notes(cfg.get("resume_clusters"))


def default_resume(cfg):
    return cfg.get("default_resume")


def score_thresholds(cfg):
    t = cfg.get("score_thresholds", {})
    return {
        "apply": int(t.get("apply", 65)),
        "maybe": int(t.get("maybe", 45)),
        "normalizer": float(t.get("normalizer", 40) or 40),
    }


def github_sources(cfg):
    """Return [{'id', 'url', 'parser'}, ...] from config.github_sources.
    Each value may be a {'url','parser'} object or a bare url string (parser
    defaults to 'md')."""
    out = []
    for k, v in _strip_notes(cfg.get("github_sources")).items():
        if isinstance(v, dict):
            out.append({"id": k, "url": v.get("url"), "parser": v.get("parser", "md")})
        else:
            out.append({"id": k, "url": v, "parser": "md"})
    return out


def llm_profile(cfg):
    return cfg.get("llm_profile", {})
