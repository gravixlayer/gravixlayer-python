"""Version metadata (optional helper; canonical version is in pyproject.toml and gravixlayer.__version__)."""

__version__ = "0.1.0"
__version_info__ = tuple(int(x) for x in __version__.split("."))

VERSION_HISTORY = {
    "0.1.0": "First public SDK release (0.1.x line).",
}


def get_version_info():
    """Return current version metadata."""
    return {
        "version": __version__,
        "version_info": __version_info__,
        "description": VERSION_HISTORY.get(__version__, "No description available"),
    }
