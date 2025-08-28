"""Version information for GravixLayer SDK"""

__version__ = "0.0.22"
__version_info__ = tuple(int(x) for x in __version__.split('.'))

# Version history
VERSION_HISTORY = {
    "0.0.2": "Initial release with OpenAI compatibility",
    # Add future versions here
}

def get_version_info():
    """Get current version information"""
    return {
        "version": __version__,
        "version_info": __version_info__,
        "description": VERSION_HISTORY.get(__version__, "No description available")
    }
