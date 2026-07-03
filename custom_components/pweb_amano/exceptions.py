"""Exceptions for the PWEB Amano integration."""


class PwebAmanoError(Exception):
    """Base exception for PWEB Amano."""


class PwebAmanoAuthError(PwebAmanoError):
    """Login was rejected by the portal."""


class PwebAmanoConnectionError(PwebAmanoError):
    """The portal could not be reached."""
