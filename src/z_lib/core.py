import atexit
from typing import Dict, List, Optional, Union, IO
from pathlib import Path

from ._types import ZipHandle, OpenMode
from .exceptions import ZipNotLoadedError, ZipAlreadyLoadedError, ZipPathError
from .path_resolver import normalize_path, resolve_to_real_path
from .backend.zipfile_backend import ZipFileBackend
from .namespaces.z_os import Z_OS
from .namespaces.z_shutil import Z_Shutil

class Z_Lib:
    def __init__(self):
        self._loaded_zips: Dict[str, ZipHandle] = {}
        self._backend = ZipFileBackend()
        
        # Ensure cleanup on exit
        atexit.register(self._cleanup)
        
        self.os = Z_OS(self)
        self.shutil = Z_Shutil(self)

    def load_zip(self, *paths: str, create: bool = False, mode: OpenMode = "rw") -> None:
        """
        Load one or more ZIP files.
        """
        for path in paths:
            # 正規化だけでなく、絶対パスに解決して一貫性を持たせる
            abs_path = Path(path).resolve()
            norm_path = normalize_path(str(abs_path))
            
            if norm_path in self._loaded_zips:
                continue
                
            handle = self._backend.open(path, create=create, mode=mode)
            self._loaded_zips[norm_path] = handle

    def unload_zip(self, *paths: str) -> None:
        """
        Unload one or more ZIP files, saving changes if mode is "rw".
        """
        for path in paths:
            abs_path = Path(path).resolve()
            norm_path = normalize_path(str(abs_path))
            
            if norm_path not in self._loaded_zips:
                continue
                
            handle = self._loaded_zips[norm_path]
            # Save logic is handled by backend based on handle's mode
            # But we can explicitly control 'save' flag if we wanted force-discard.
            # Default behavior: save if rw.
            self._backend.close(handle, save=True)
            
            del self._loaded_zips[norm_path]

    def swap_zip(self, target_zips: List[str], create: bool = False, mode: OpenMode = "rw") -> None:
        """
        Synchronize loaded ZIPs with the target list.
        Unloads ZIPs not in target_zips, loads ZIPs in target_zips that aren't loaded.
        """
        target_norm_set = {normalize_path(p) for p in target_zips}
        current_norm_set = set(self._loaded_zips.keys())
        
        # Unload
        to_unload = current_norm_set - target_norm_set
        if to_unload:
            self.unload_zip(*to_unload)
            
        # Load
        to_load = target_norm_set - current_norm_set
        if to_load:
            # Note: We pass original paths? No, we only have normalized ones in set.
            # We should probably iterate target_zips to preserve original strings for open()
            # or just use normalized strings.
            # Let's use the provided target_zips list to find ones that need loading.
            
            zips_to_load_args = []
            for raw_path in target_zips:
                if normalize_path(raw_path) in to_load:
                    zips_to_load_args.append(raw_path)
            
            if zips_to_load_args:
                self.load_zip(*zips_to_load_args, create=create, mode=mode)

    def load_nest(self, folder: str, create: bool = False, mode: OpenMode = "r") -> None:
        """
        Recursively find and load all .zip files in a folder.
        Default mode is "r" as per requirements.
        """
        folder_path = Path(folder)
        if not folder_path.exists():
             if create:
                 folder_path.mkdir(parents=True, exist_ok=True)
             else:
                 raise FileNotFoundError(f"Folder not found: {folder}")

        # RGlob for all zip files
        # Note: pattern match is case sensitive on Linux, case insensitive on Windows usually.
        # We'll use glob with standard "*.zip".
        for zip_file in folder_path.rglob("*.zip"):
            self.load_zip(str(zip_file), create=create, mode=mode)

    def open(self, path: str, mode: str = "r", **kwargs) -> IO:
        """
        Open a file (local or inside ZIP) seamlessly.
        """
        # Resolve to real path (temp path if in ZIP, absolute path if local)
        real_path = resolve_to_real_path(path, self._loaded_zips)
        return open(real_path, mode, **kwargs)

    def resolve(self, path: str) -> Path:
        """
        Resolve a virtual path to a real filesystem path (Path object).
        Useful for integration with libraries like Polars, Pillow, xlwings.
        """
        return resolve_to_real_path(path, self._loaded_zips)

    def _cleanup(self) -> None:
        """
        Force unload all ZIPS (cleanup).
        """
        # Create a list of keys to avoid runtime error during modification
        for zip_path in list(self._loaded_zips):
            self.unload_zip(zip_path)

    def __del__(self) -> None:
        self._cleanup()
