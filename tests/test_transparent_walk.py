"""
透過 walk のテスト:
  z.os.walk("parentFolder/") でフォルダを走査した際に、
  ロード済みZIPファイルを自動的にディレクトリとして展開することを確認する。
"""
import os
import zipfile
import pytest
from z_lib.core import Z_Lib
from z_lib.path_resolver import normalize_path

@pytest.fixture
def z_lib_instance():
    z = Z_Lib()
    yield z
    z._cleanup()

@pytest.fixture
def nested_structure(tmp_path):
    """
    フォルダ構成:
    root/
      local_file.txt
      local_sub/
        local2.txt
      archive.zip/
        img/
          item01.txt
        readme.txt
    """
    root = tmp_path / "root"
    root.mkdir()
    (root / "local_file.txt").write_text("local")
    sub = root / "local_sub"
    sub.mkdir()
    (sub / "local2.txt").write_text("sub content")

    zp = root / "archive.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("img/item01.txt", "img content")
        zf.writestr("readme.txt", "readme content")

    return root

def test_transparent_walk_from_parent(z_lib_instance, nested_structure):
    """
    親フォルダを起点に walk して、ロード済みZIPが透過的に展開されることを確認する。
    """
    zip_path = str(nested_structure / "archive.zip")
    z_lib_instance.load_zip(zip_path, mode="r")

    root_virtual = normalize_path(str(nested_structure))
    norm_zip_path = normalize_path(zip_path)

    all_roots = {}
    for root, dirs, files in z_lib_instance.os.walk(str(nested_structure)):
        norm_root = normalize_path(root)
        all_roots[norm_root] = (dirs, files)
        print(f"Root: {norm_root}, Dirs: {dirs}, Files: {files}")

    # ルートには local_file.txt と archive.zip (擬似ディレクトリ) が見えるはず
    assert root_virtual in all_roots
    root_dirs, root_files = all_roots[root_virtual]
    assert "local_sub" in root_dirs
    assert "archive.zip" in root_dirs   # ZIPがディレクトリとして見えている
    assert "local_file.txt" in root_files
    assert "archive.zip" not in root_files  # ファイルには含まれない

    # ZIPの中身が透過的に展開されている
    assert norm_zip_path in all_roots
    zip_dirs, zip_files = all_roots[norm_zip_path]
    assert "img" in zip_dirs
    assert "readme.txt" in zip_files

    # さらにZIP内サブフォルダも展開
    assert f"{norm_zip_path}/img" in all_roots
    img_dirs, img_files = all_roots[f"{norm_zip_path}/img"]
    assert "item01.txt" in img_files


def test_transparent_walk_japanese_path(z_lib_instance, tmp_path):
    """
    日本語・特殊文字を含むZIPパスでも透過 walk が機能することを確認する。
    """
    zip_dir = tmp_path / "zip"
    zip_dir.mkdir()
    zip_name = "yyyymmdd-2【サプライヤ】エントリー（商品画像ファイル）.zip"
    zip_path = str(zip_dir / zip_name)

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("画像/item01.jpg", b"image_data")
        zf.writestr("画像/item02.jpg", b"image_data")
        zf.writestr("readme.txt", b"explanation")

    z_lib_instance.load_zip(zip_path, mode="r")
    norm_zip = normalize_path(zip_path)

    all_roots = {}
    for root, dirs, files in z_lib_instance.os.walk(str(zip_dir)):
        all_roots[normalize_path(root)] = (dirs, files)

    norm_dir = normalize_path(str(zip_dir))
    # ZIPがディレクトリとして見えている
    assert zip_name in all_roots[norm_dir][0]
    # ZIP内の構造が展開されている
    assert norm_zip in all_roots
    assert "画像" in all_roots[norm_zip][0]
    assert f"{norm_zip}/画像" in all_roots
    assert "item01.jpg" in all_roots[f"{norm_zip}/画像"][1]


def test_os_path_exists_deepest_level(z_lib_instance, tmp_path):
    """
    最深部パスに対して os.path.exists() が正常に機能することを確認する。
    """
    zip_dir = tmp_path / "zip"
    zip_dir.mkdir()
    zip_name = "yyyymmdd-2【サプライヤ】エントリー（商品画像ファイル）.zip"
    zip_path = str(zip_dir / zip_name)

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("画像/item01.jpg", b"image_data_01")
        zf.writestr("画像/item02.jpg", b"image_data_02")
        zf.writestr("readme.txt", b"explanation")

    z_lib_instance.load_zip(zip_path, mode="r")

    # 存在するパス
    assert z_lib_instance.os.path.exists(f"{zip_path}/画像/item01.jpg")
    assert z_lib_instance.os.path.exists(f"{zip_path}/画像/item02.jpg")
    assert z_lib_instance.os.path.exists(f"{zip_path}/readme.txt")
    assert z_lib_instance.os.path.exists(f"{zip_path}/画像")    # ディレクトリ
    assert z_lib_instance.os.path.exists(zip_path)              # ZIPルートも

    # 存在しないパス
    assert not z_lib_instance.os.path.exists(f"{zip_path}/画像/item99.jpg")
    assert not z_lib_instance.os.path.exists(f"{zip_path}/nonexistent_folder")

    # isfile / isdir の確認
    assert z_lib_instance.os.path.isfile(f"{zip_path}/画像/item01.jpg")
    assert z_lib_instance.os.path.isdir(f"{zip_path}/画像")
    assert not z_lib_instance.os.path.isfile(f"{zip_path}/画像")
    assert not z_lib_instance.os.path.isdir(f"{zip_path}/画像/item01.jpg")
