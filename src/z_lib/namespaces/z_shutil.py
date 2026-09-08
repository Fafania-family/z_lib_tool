import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core import Z_Lib


class Z_Shutil:
    def __init__(self, z_lib: "Z_Lib"):
        self._z_lib = z_lib

    def copy2(self, src: str, dst: str, **kwargs) -> str:
        session_dst = self._z_lib._get_session_for_path(dst)
        if session_dst:
            session_dst.check_writable("copy2")

        real_src = self._z_lib.resolve(src)
        real_dst = self._z_lib.resolve(dst)
        self._z_lib._log(f"  📌 [Z_SHUTIL] copy2   {src}  ➜  {dst}")
        result = shutil.copy2(real_src, real_dst, **kwargs)

        if session_dst:
            session_dst.mark_dirty()
        return str(result)

    def move(self, src: str, dst: str, **kwargs) -> str:
        session_src = self._z_lib._get_session_for_path(src)
        session_dst = self._z_lib._get_session_for_path(dst)
        if session_src:
            session_src.check_writable("move (source)")
        if session_dst:
            session_dst.check_writable("move (destination)")

        real_src = self._z_lib.resolve(src)
        real_dst = self._z_lib.resolve(dst)
        self._z_lib._log(f"  ➡️  [Z_SHUTIL] move   {src}  ➜  {dst}")
        result = shutil.move(real_src, real_dst, **kwargs)

        if session_src:
            session_src.mark_dirty()
        if session_dst and session_dst != session_src:
            session_dst.mark_dirty()
        return str(result)

    def copytree(self, src: str, dst: str, **kwargs) -> str:
        session_dst = self._z_lib._get_session_for_path(dst)
        if session_dst:
            session_dst.check_writable("copytree")

        real_src = self._z_lib.resolve(src)
        real_dst = self._z_lib.resolve(dst)
        self._z_lib._log(f"  🗂  [Z_SHUTIL] copytree   {src}  ➜  {dst}")
        result = shutil.copytree(real_src, real_dst, **kwargs)

        if session_dst:
            session_dst.mark_dirty()
        return str(result)

    def rmtree(self, path: str, **kwargs) -> None:
        session = self._z_lib._get_session_for_path(path)
        if session:
            session.check_writable("rmtree")

        real_path = self._z_lib.resolve(path)
        self._z_lib._log(f"  🗑  [Z_SHUTIL] rmtree   › {path}")
        shutil.rmtree(real_path, **kwargs)

        if session:
            session.mark_dirty()
