"""Errors shared by services."""


class ConflictError(RuntimeError):
    """The request clashes with the current state (cooking a batch twice, changing a finished trip): 409."""
