import os
import zipfile
import pytest
from pathlib import Path
from z_lib.core import Z_Lib
from z_lib.path_resolver import normalize_path

@pytest.fixture
def z_lib_instance():
    z = Z_Lib()
    yield z
    z._cleanup()

def test_relative_vs_absolute_access(z_lib_instance, tmp_path):
    # テスト用ZIP作成
    zip_name = "test.zip"
    zip_path = tmp_path / zip_name
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("hello.txt", "world")

    # カレントディレクトリを一時ディレクトリに移動して相対パスをシミュレート
    os.chdir(tmp_path)
    
    # 1. 相対パスでロード
    rel_path = zip_name
    z_lib_instance.load_zip(rel_path)
    
    # 相対パスでのアクセス -> 成功するはず
    assert z_lib_instance.os.path.exists(f"{rel_path}/hello.txt")
    
    # 絶対パスでのアクセス -> 現状の実装では失敗する可能性がある（キーが相対パスのため）
    abs_path = normalize_path(str(zip_path.resolve()))
    print(f"Loaded key: {rel_path}")
    print(f"Accessing with: {abs_path}/hello.txt")
    
    # ここで成功するか確認 (修正後のロジックでは成功するはず)
    assert z_lib_instance.os.path.exists(f"{abs_path}/hello.txt")

def test_absolute_load_relative_access(z_lib_instance, tmp_path):
    zip_name = "test_abs.zip"
    zip_path = tmp_path / zip_name
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("hello.txt", "world")

    os.chdir(tmp_path)
    
    # 2. 絶対パスでロード
    abs_path = normalize_path(str(zip_path.resolve()))
    z_lib_instance.load_zip(abs_path)
    
    # 絶対パスでのアクセス -> 成功
    assert z_lib_instance.os.path.exists(f"{abs_path}/hello.txt")
    
    # 相対パスでのアクセス -> 修正後のロジックでは成功するはず
    rel_path = zip_name
    print(f"Loaded key: {abs_path}")
    print(f"Accessing with: {rel_path}/hello.txt")
    
    assert z_lib_instance.os.path.exists(f"{rel_path}/hello.txt")
