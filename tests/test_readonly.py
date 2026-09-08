import pytest
import zipfile
from pathlib import Path

from z_lib.core import Z_Lib
from z_lib.exceptions import ZipReadOnlyError, ZipSecurityError


@pytest.fixture
def test_zip_with_data(tmp_path):
    zip_path = tmp_path / "readonly_sample.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("file1.txt", "data 1")
        zf.writestr("subdir/file2.txt", "data 2")
    return zip_path


def test_default_mode_is_readonly(tmp_path, test_zip_with_data):
    z = Z_Lib()
    z.load_zip(str(test_zip_with_data))

    status = z.get_status(str(test_zip_with_data))
    assert status is not None
    assert status["mode"] == "r"

    # 読み取りは成功する
    with z.open(f"{test_zip_with_data}/file1.txt", "r") as fp:
        assert fp.read() == "data 1"

    # 書き込みは拒否される
    with pytest.raises(ZipReadOnlyError):
        with z.open(f"{test_zip_with_data}/file1.txt", "w") as fp:
            fp.write("overwrite")

    with pytest.raises(ZipReadOnlyError):
        z.os.mkdir(f"{test_zip_with_data}/new_folder")

    with pytest.raises(ZipReadOnlyError):
        z.os.remove(f"{test_zip_with_data}/file1.txt")

    dummy_local = tmp_path / "external.txt"
    dummy_local.write_text("local")

    with pytest.raises(ZipReadOnlyError):
        z.shutil.copy2(str(dummy_local), f"{test_zip_with_data}/external.txt")

    z.close()

    # 元ZIPが変更されていないことを確認
    with zipfile.ZipFile(test_zip_with_data, "r") as zf:
        assert zf.namelist() == ["file1.txt", "subdir/file2.txt"]
        assert zf.read("file1.txt") == b"data 1"


def test_directory_traversal_prevention(tmp_path):
    z = Z_Lib()
    safe_zip = tmp_path / "safe.zip"
    with zipfile.ZipFile(safe_zip, "w") as zf:
        zf.writestr("normal.txt", "ok")

    z.load_zip(str(safe_zip))

    with pytest.raises(ZipSecurityError):
        z.resolve(f"{safe_zip}/../escaped.txt")

    with pytest.raises(ZipSecurityError):
        z.resolve(f"{safe_zip}/subdir/../../escaped.txt")

    z.close()
