"""
Configuration package.
"""

from cryptobot.config.settings import settings, load_settings

# Export the settings object as config for backward compatibility
config = settings

__all__ = ["settings", "load_settings", "config"]