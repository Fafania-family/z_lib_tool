import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from .._types import ZipHandle, OpenMode
from ..exceptions import ZipPathError

# Windows製ZIPはCP932(Shift-JIS)でエンコードされているが、
# Python の zipfile は UTF-8 フラグなしのエントリを CP437 として扱うため文字化けが発生する。
# このフラグで UTF-8 フラグの有無を確認し、なければ CP437バイト列 を CP932 として再デコードする。
_FLAG_UTF8 = 0x800


def _decode_zip_filename(info: zipfile.ZipInfo) -> str:
    """
    ZIPエントリ名を正しくデコードして返す。

    - UTF-8フラグ(bit11)が立っている場合: そのまま返す（zipfileが正しく処理済み）
    - そうでない場合: CP437として読まれたバイト列をCP932として再デコードする
    """
    if info.flag_bits & _FLAG_UTF8:
        # zipfile が UTF-8 として正しくデコード済み
        return info.filename

    # zipfile は UTF-8 フラグなしのエントリを CP437 として読むので、
    # 一度 CP437 のバイト列に戻してから CP932 として解釈する
    raw_bytes = info.filename.encode("cp437")
    try:
        return raw_bytes.decode("cp932")
    except (UnicodeDecodeError, ValueError):
        # CP932 でも失敗した場合は元の文字列を返す（フォールバック）
        return info.filename


def _extract_with_encoding(zf: zipfile.ZipFile, dest_dir: str) -> None:
    """
    文字化け対策済みのZIP展開処理。
    各エントリ名を正しくデコードしてからdest_dirへ展開する。
    """
    for info in zf.infolist():
        correct_name = _decode_zip_filename(info)
        dest_path = Path(dest_dir) / correct_name

        if correct_name.endswith("/"):
            # ディレクトリエントリ
            dest_path.mkdir(parents=True, exist_ok=True)
        else:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(dest_path, "wb") as dst:
                shutil.copyfileobj(src, dst)


class ZipFileBackend:
    def open(self, path: str, create: bool, mode: OpenMode = "rw") -> ZipHandle:
        path_obj = Path(path).resolve()

        if not path_obj.exists():
            if not create:
                raise FileNotFoundError(f"ZIP file not found: {path}")

        # 一時ディレクトリを作成
        temp_dir = tempfile.mkdtemp(prefix="z_lib_")

        if path_obj.exists() and zipfile.is_zipfile(path_obj):
            # 文字化け対策済みの展開関数を使用
            with zipfile.ZipFile(path_obj, "r") as zf:
                _extract_with_encoding(zf, temp_dir)
        elif path_obj.exists() and not zipfile.is_zipfile(path_obj):
            shutil.rmtree(temp_dir)
            raise ZipPathError(f"File exists but is not a valid ZIP file: {path}")

        return ZipHandle(
            path=str(path_obj),
            temp_dir=temp_dir,
            mode=mode,
        )

    def close(self, handle: ZipHandle, save: bool) -> None:
        temp_dir = Path(handle["temp_dir"])
        original_path = Path(handle["path"])
        mode = handle["mode"]

        try:
            if save and mode == "rw" and temp_dir.exists():
                if not original_path.parent.exists():
                    original_path.parent.mkdir(parents=True, exist_ok=True)

                fd, temp_zip_path = tempfile.mkstemp(
                    dir=original_path.parent, suffix=".tmp_zip"
                )
                os.close(fd)

                try:
                    with zipfile.ZipFile(
                        temp_zip_path, "w", compression=zipfile.ZIP_DEFLATED
                    ) as zf:
                        for root, _dirs, files in os.walk(temp_dir):
                            for file in files:
                                file_path = Path(root) / file
                                arcname = file_path.relative_to(temp_dir)
                                zf.write(file_path, arcname)

                    shutil.move(temp_zip_path, original_path)

                except Exception:
                    if os.path.exists(temp_zip_path):
                        os.remove(temp_zip_path)
                    raise

        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
