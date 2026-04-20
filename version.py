"""Version metadata (optional helper; canonical version is in pyproject.toml and gravixlayer.__version__)."""

__version__ = "0.1.39"
__version_info__ = tuple(int(x) for x in __version__.split("."))

VERSION_HISTORY = {
    "0.1.0": "First public SDK release (0.1.x line).",
    "0.1.1": "Republish on PyPI; 0.1.0 artifacts cannot be re-uploaded (filename reuse policy).",
}


def get_version_info():
    """Return current version metadata."""
    return {
        "version": __version__,
        "version_info": __version_info__,
        "description": VERSION_HISTORY.get(__version__, "No description available"),
    }
