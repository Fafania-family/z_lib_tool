import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from ._types import FileMetadata
from .exceptions import ZipConflictError


def get_file_metadata(path: Path) -> FileMetadata:
    if not path.exists():
        return FileMetadata(mtime=0.0, size=0, exists=False)
    stat = path.stat()
    return FileMetadata(mtime=stat.st_mtime, size=stat.st_size, exists=True)


def check_conflict(original_path: Path, expected_meta: FileMetadata) -> None:
    current_meta = get_file_metadata(original_path)
    if not expected_meta["exists"] and current_meta["exists"]:
        raise ZipConflictError(
            f"Target ZIP was created externally while loaded: {original_path}"
        )
    if expected_meta["exists"]:
        if not current_meta["exists"]:
            raise ZipConflictError(
                f"Target ZIP was deleted externally while loaded: {original_path}"
            )
        # Windowsのmtime精度（100ns）やFAT/ネットワークドライブのタイムスタンプ差異を吸収するため微小誤差を許容
        if abs(current_meta["mtime"] - expected_meta["mtime"]) > 0.001 or current_meta["size"] != expected_meta["size"]:
            raise ZipConflictError(
                f"Target ZIP was modified externally while loaded: {original_path} "
                f"(expected mtime={expected_meta['mtime']}, size={expected_meta['size']}, "
                f"current mtime={current_meta['mtime']}, size={current_meta['size']})"
            )


def copy_to_local(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def atomic_replace(local_source: Path, target_destination: Path) -> None:
    target_destination.parent.mkdir(parents=True, exist_ok=True)
    # Box Drive等のクラウド同期ドライブでは異なるドライブレター間や仮想マウントへの直接 os.replace が
    # EXDEV (Invalid cross-device link) または PermissionError になる場合があるため、
    # 対象フォルダ内に一度安全な一時ファイルを作成してからアトミックに置換する。
    temp_in_target_dir = None
    try:
        fd, temp_path_str = tempfile.mkstemp(
            dir=target_destination.parent,
            prefix=".z_lib_tmp_",
            suffix=".zip"
        )
        os.close(fd)
        temp_in_target_dir = Path(temp_path_str)
        shutil.copy2(local_source, temp_in_target_dir)
        os.replace(temp_in_target_dir, target_destination)
    finally:
        if temp_in_target_dir and temp_in_target_dir.exists():
            try:
                temp_in_target_dir.unlink()
            except OSError:
                pass
