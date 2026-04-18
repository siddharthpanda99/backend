"""
Nexus CLI - Consolidated command-line interface for Nexus AI Platform.

Usage:
    nexus agent create my_agent
    nexus agent list
    nexus sync init
    nexus chat [message]
"""

from cli.main import cli

__all__ = ["cli"]
