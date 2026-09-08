from typing import Optional


class ZipNotLoadedError(Exception):
    """Raised when attempting to access a ZIP file that has not been loaded."""
    pass


class ZipAlreadyLoadedError(Exception):
    """Raised when attempting to load a ZIP file that is already loaded."""
    pass


class ZipPathError(Exception):
    """Raised when a path is invalid or cannot be resolved to a ZIP file."""
    pass


class ZipReadOnlyError(Exception):
    """Raised when an operation attempts to modify a ZIP loaded in read-only mode."""
    pass


class ZipConflictError(Exception):
    """Raised when the original ZIP file has been modified externally after being loaded."""
    pass


class ZipSecurityError(Exception):
    """Raised when a malicious or unsafe path (e.g. Zip Slip directory traversal) is detected."""
    pass


class ZipSaveError(Exception):
    """Raised when recompression, validation, or writing back the ZIP file fails."""
    def __init__(self, message: str, recovery_path: Optional[str] = None):
        super().__init__(message)
        self.recovery_path = recovery_path
