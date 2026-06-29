"""Importing this package registers all built-in notifier adapters.

Add a channel by creating a module here and importing it below (see
docs/recipes.md).
"""

from app.notifiers.adapters import discord, email, ntfy, slack, telegram, webhook

__all__ = ["discord", "email", "ntfy", "slack", "telegram", "webhook"]
