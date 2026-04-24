"""Leapmotor API exception hierarchy."""

from __future__ import annotations


class LeapmotorApiError(Exception):
    """Base Leapmotor API error."""


class LeapmotorAuthError(LeapmotorApiError):
    """Leapmotor authentication failed."""


class LeapmotorAccountCertError(LeapmotorAuthError):
    """Leapmotor account certificate could not be opened."""


class LeapmotorMissingAppCertError(LeapmotorAuthError):
    """Local app certificate material is missing."""
