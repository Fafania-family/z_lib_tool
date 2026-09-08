import zipfile
from pathlib import Path
from z_lib.core import Z_Lib


def make_cp932_raw_zip(path: Path, filename: str, content: bytes) -> None:
    """
    Windows標準のzip作成機能が生成するような、
    UTF-8フラグなし・CP932生バイト列でダメ文字を含むZIPを忠実に再現して作成する。
    """
    raw_name = filename.encode("cp932")
    placeholder = "X" * len(raw_name)

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(placeholder, content)

    with open(path, "rb") as fp:
        data = bytearray(fp.read())

    # Local File Header の flag_bits (offset 6..8) を 0 にクリア
    data[6] = 0
    data[7] = 0

    # Central Directory Header の flag_bits (offset + 8) を 0 にクリア
    cd_pos = data.find(b"PK\x01\x02")
    if cd_pos != -1:
        data[cd_pos + 8] = 0
        data[cd_pos + 9] = 0

    # プレースホルダーをCP932の生バイト列に置換
    data = data.replace(placeholder.encode("ascii"), raw_name)

    with open(path, "wb") as fp:
        fp.write(data)


def test_cp932_dame_moji_preservation(tmp_path):
    zip_path = tmp_path / "japanese_dame.zip"

    # 「表」(0x95 0x5c), 「能」(0x94 0x5c) は2バイト目に 0x5c (\) を持つダメ文字
    make_cp932_raw_zip(zip_path, "予定表.txt", "スケジュールデータ".encode("utf-8"))

    z = Z_Lib()
    z.load_zip(str(zip_path), mode="rw")

    # 透過的なファイル一覧取得
    files = z.os.listdir(str(zip_path))
    assert "予定表.txt" in files

    # 読み取り
    with z.open(f"{zip_path}/予定表.txt", "r", encoding="utf-8") as fp:
        assert fp.read() == "スケジュールデータ"

    # 新たにダメ文字ファイルを追加してcommit
    with z.open(f"{zip_path}/代表者一覧.txt", "w", encoding="utf-8") as fp:
        fp.write("山田太郎")

    z.commit(str(zip_path))
    z.close(str(zip_path))

    # 再度ロードして日本語が維持されていることを確認
    z2 = Z_Lib()
    z2.load_zip(str(zip_path), mode="r")
    assert z2.os.path.exists(f"{zip_path}/予定表.txt")
    assert z2.os.path.exists(f"{zip_path}/代表者一覧.txt")
    with z2.open(f"{zip_path}/代表者一覧.txt", "r", encoding="utf-8") as fp:
        assert fp.read() == "山田太郎"
    z2.close()
