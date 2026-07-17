"""Offline autonomy-policy research arena.

Nothing in this package opens the camera, UART, Hailo device, or network.
"""

from .candidate import Policy

__all__ = ["Policy"]
