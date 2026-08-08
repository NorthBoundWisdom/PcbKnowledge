"""Compatibility ASGI import for deployment tooling."""

from pcbknowledge.api import app, create_app, main

__all__ = ["app", "create_app", "main"]
