from typing import TypedDict, Literal, IO, Callable, Optional
from pathlib import Path

OpenMode = Literal["r", "rw"]
SessionStatus = Literal["loaded", "dirty", "committed", "closed", "failed"]

# ProgressCallback(phase: str, progress: float, detail: str)
ProgressCallback = Callable[[str, float, str], None]


class FileMetadata(TypedDict):
    mtime: float
    size: int
    exists: bool


class ZipHandle(TypedDict):
    path: str              # Original ZIP file path
    temp_dir: str          # Path to the temporary directory where ZIP is extracted
    mode: OpenMode         # "r" or "rw"

