"""Centralized authentication package for the Subbuteo suite."""

from .login import (
    get_current_user,
    logout_button,
    require_auth,
    show_auth_screen,
    verify_write_access,
)
