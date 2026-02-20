import os
from typing import Any, Iterator, List, Tuple, TYPE_CHECKING
from pathlib import Path
from ..path_resolver import normalize_path
from .z_os_path import Z_OS_Path

if TYPE_CHECKING:
    from ..core import Z_Lib

class Z_OS:
    def __init__(self, z_lib: "Z_Lib"):
        self._z_lib = z_lib
        self.path = Z_OS_Path(z_lib)

    def listdir(self, path: str) -> List[str]:
        real_path = self._z_lib.resolve(path)
        return os.listdir(real_path)

    def mkdir(self, path: str, mode: int = 0o777) -> None:
        real_path = self._z_lib.resolve(path)
        os.mkdir(real_path, mode)
        
    def makedirs(self, path: str, mode: int = 0o777, exist_ok: bool = False) -> None:
        real_path = self._z_lib.resolve(path)
        os.makedirs(real_path, mode, exist_ok)

    def remove(self, path: str) -> None:
        real_path = self._z_lib.resolve(path)
        os.remove(real_path)
        
    def rmdir(self, path: str) -> None:
        real_path = self._z_lib.resolve(path)
        os.rmdir(real_path)

    def rename(self, src: str, dst: str) -> None:
        real_src = self._z_lib.resolve(src)
        real_dst = self._z_lib.resolve(dst)
        os.rename(real_src, real_dst)

    def walk(self, top: str, topdown: bool = True, onerror: Any = None, followlinks: bool = False) -> Iterator[Tuple[str, List[str], List[str]]]:
        """
        透過的なディレクトリ木ジェネレータ。
        ローカルディレクトリを走査する際に、ロード済みZIPファイルを
        自動的にディレクトリとして展開して返す。
        Yields: (仮想パス, サブディレクトリ名リスト, ファイル名リスト)
        """
        yield from self._walk_recursive(normalize_path(top), topdown, onerror, followlinks)

    def _walk_recursive(
        self, virtual_top: str, topdown: bool, onerror: Any, followlinks: bool
    ) -> Iterator[Tuple[str, List[str], List[str]]]:
        """
        再帰的 walk の実装。
        - ロード済みZIPのパスに一致する場合 → ZIPの一時ディレクトリを起点に走査
        - ローカルディレクトリの場合 → os.listdir で一覧を取得し、
          ロード済みZIPファイルをディレクトリとして扱い再帰する
        """
        loaded_zips = self._z_lib._loaded_zips  # Dict[str, ZipHandle]

        # --- ケース1: virtual_top がロード済みZIPのパスに完全一致 or その内部パス ---
        from ..path_resolver import find_longest_match_handle
        handle, internal_path = find_longest_match_handle(virtual_top, loaded_zips)

        if handle:
            # ZIPの一時ディレクトリを起点にローカルwalkし、仮想パスに変換して yield
            real_top = Path(handle["temp_dir"]) / internal_path
            for root, dirs, files in os.walk(real_top, topdown=topdown, onerror=onerror, followlinks=followlinks):
                try:
                    rel = Path(root).relative_to(Path(handle["temp_dir"]))
                except ValueError:
                    continue
                # rel は ZIPのキー (ロード時のパス) からの相対位置を意味する
                # virtual path = [zip_key] / [rel]
                zip_key = next(
                    k for k, v in loaded_zips.items() if v["temp_dir"] == handle["temp_dir"]
                )
                if str(rel) == ".":
                    virtual_root = zip_key
                else:
                    virtual_root = f"{zip_key}/{normalize_path(str(rel))}"
                yield virtual_root, dirs, files
            return

        # --- ケース2: ローカルディレクトリ ---
        real_top = Path(virtual_top).resolve()
        if not real_top.is_dir():
            if onerror:
                onerror(OSError(f"Not a directory: {virtual_top}"))
            return

        try:
            entries = list(real_top.iterdir())
        except OSError as e:
            if onerror:
                onerror(e)
            return

        # ロード済みZIPキーを正規化済みセットとして準備
        loaded_zip_norms = set(loaded_zips.keys())

        sub_dirs: List[str] = []
        sub_files: List[str] = []
        # エントリを仕分け：ロード済みZIPはディレクトリ扱い
        zip_entries: List[str] = []  # このディレクトリ内のロード済みZIP名

        for entry in entries:
            norm_entry = normalize_path(str(entry.resolve()))
            if entry.is_dir() and not (entry.is_symlink() and not followlinks):
                sub_dirs.append(entry.name)
            elif norm_entry in loaded_zip_norms:
                # ロード済みZIPをディレクトリとして扱う
                zip_entries.append(entry.name)
            else:
                sub_files.append(entry.name)

        # topdown=True: 先に現在ディレクトリを yield し、その後再帰
        # dirs に zip_entries を含める（ユーザーが dirs を編集できるよう）
        virtual_dirs = sub_dirs + zip_entries

        if topdown:
            yield virtual_top, virtual_dirs, sub_files

        # ローカルサブディレクトリを再帰
        for d in sub_dirs:
            child_virtual = f"{virtual_top}/{d}"
            yield from self._walk_recursive(child_virtual, topdown, onerror, followlinks)

        # ロード済みZIPを再帰（ディレクトリとして展開）
        for zname in zip_entries:
            child_virtual = normalize_path(str((real_top / zname).resolve()))
            yield from self._walk_recursive(child_virtual, topdown, onerror, followlinks)

        if not topdown:
            yield virtual_top, virtual_dirs, sub_files
