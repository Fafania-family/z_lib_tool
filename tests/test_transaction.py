import os
import time
import zipfile
from pathlib import Path
import pytest

from z_lib.core import Z_Lib
from z_lib.exceptions import ZipConflictError, ZipReadOnlyError


def test_commit_and_rollback(tmp_path):
    zip_path = tmp_path / "transaction.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("original.txt", "initial")

    z = Z_Lib()
    z.load_zip(str(zip_path), mode="rw")

    # ファイルを編集
    with z.open(f"{zip_path}/original.txt", "w") as fp:
        fp.write("modified")

    status = z.get_status(str(zip_path))
    assert status["is_dirty"] is True

    # rollback を実行して元に戻す
    z.rollback(str(zip_path))
    status_after = z.get_status(str(zip_path))
    assert status_after["is_dirty"] is False

    with z.open(f"{zip_path}/original.txt", "r") as fp:
        assert fp.read() == "initial"

    # 再度編集して今度は commit
    with z.open(f"{zip_path}/original.txt", "w") as fp:
        fp.write("final_version")
    z.commit(str(zip_path))

    z.close(str(zip_path))

    # ディスク上の元ZIPが更新されたことを確認
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert zf.read("original.txt") == b"final_version"


def test_edit_context_manager_success(tmp_path):
    zip_path = tmp_path / "context.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data.txt", "before")

    z = Z_Lib()
    with z.edit(str(zip_path)):
        with z.open(f"{zip_path}/data.txt", "w") as fp:
            fp.write("after")

    # コンテキスト終了後に自動でcommitおよびクローズされている
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert zf.read("data.txt") == b"after"


def test_edit_context_manager_exception_protection(tmp_path):
    zip_path = tmp_path / "protected.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("safe.txt", "original_intact")

    z = Z_Lib()
    with pytest.raises(ValueError):
        with z.edit(str(zip_path)):
            with z.open(f"{zip_path}/safe.txt", "w") as fp:
                fp.write("corrupted_tentative")
            raise ValueError("Unexpected processing failure")

    # 例外により変更が破棄され、元ZIPが保護されていること
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert zf.read("safe.txt") == b"original_intact"


def test_conflict_detection(tmp_path):
    zip_path = tmp_path / "conflict.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("test.txt", "v1")

    z = Z_Lib()
    z.load_zip(str(zip_path), mode="rw")

    with z.open(f"{zip_path}/test.txt", "w") as fp:
        fp.write("v2_local")

    # 外部（別のプロセスやユーザー）が元ZIPを更新した状況をシミュレート
    time.sleep(0.05)  # mtimeの差異を確実にする
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("test.txt", "v1_modified_externally")

    # 外部変更を検知してcommitが拒否されること
    with pytest.raises(ZipConflictError):
        z.commit(str(zip_path))

    z.close()


def test_empty_directory_preservation(tmp_path):
    zip_path = tmp_path / "emptydir.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("normal.txt", "text")
        # ZIP仕様におけるディレクトリエントリ（末尾 /）
        zf.writestr("empty_folder/", b"")

    z = Z_Lib()
    z.load_zip(str(zip_path), mode="rw")
    z.os.mkdir(f"{zip_path}/another_empty/")
    z.commit(str(zip_path))
    z.close(str(zip_path))

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert "empty_folder/" in names
        assert "another_empty/" in names


def test_custom_workspace_dir(tmp_path):
    custom_ws = tmp_path / "custom_temp"
    zip_path = tmp_path / "ws_test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("sample.txt", "data")

    z = Z_Lib(workspace_dir=str(custom_ws))
    z.load_zip(str(zip_path))

    status = z.get_status(str(zip_path))
    temp_dir = Path(status["temp_dir"])

    # 指定の一時ストレージ配下に作業ディレクトリが作られていることを確認
    assert custom_ws.resolve() in temp_dir.parents

    z.close()
    assert not temp_dir.exists()


def test_resolve_lifetime_and_safety(tmp_path):
    zip_path = tmp_path / "resolve_test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("read.txt", "read_only_data")

    z = Z_Lib()
    z.load_zip(str(zip_path), mode="r")

    real_path = z.resolve(f"{zip_path}/read.txt")
    assert real_path.exists()
    assert real_path.read_text() == "read_only_data"

    # resolve() された実パスを外部から直接変更しても、mode="r" の元ZIPには書き戻されない
    real_path.write_text("external_modified")
    z.close()

    assert not real_path.exists()  # close() で一時ファイルは安全に解放される
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert zf.read("read.txt") == b"read_only_data"  # 元ZIPは無傷


def test_save_error_preserves_recovery_dir(tmp_path, monkeypatch):
    from z_lib.exceptions import ZipSaveError
    import z_lib.session

    zip_path = tmp_path / "fail_save.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("doc.txt", "v1")

    z = Z_Lib()
    z.load_zip(str(zip_path), mode="rw")
    with z.open(f"{zip_path}/doc.txt", "w") as fp:
        fp.write("critical_unsaved_changes")

    # 書き戻し時に強制的に例外を発生させるモック
    def mock_atomic_replace(src, dst):
        raise OSError("Permission denied on cloud sync folder")

    monkeypatch.setattr("z_lib.session.atomic_replace", mock_atomic_replace)

    with pytest.raises(ZipSaveError) as exc_info:
        z.commit(str(zip_path))

    # エラーオブジェクトから退避パスを取得でき、編集データが残っていること
    recovery_dir = Path(exc_info.value.recovery_path)
    assert recovery_dir.exists()
    assert (recovery_dir / "doc.txt").read_text() == "critical_unsaved_changes"

    z.close(str(zip_path))
    # 失敗状態のため close() してもリカバリ用ディレクトリは破棄されずに保護される
    assert recovery_dir.exists()
