# Z_Lib

Box Drive等のクラウド同期ストレージ環境における**大量の小ファイル処理**を劇的に高速化・安全化するためのPythonライブラリです。

ZIPアーカイブを転送単位としてローカル一時領域に全展開し、標準の `os` や `shutil` ライブラリと同等のインターフェースで透過的にアクセスします。読み取り専用の安全性を担保しつつ、明示的なトランザクション（編集・コミット・ロールバック）によりクラウド上のファイル破損や競合を防ぎます。

---

## 主な特徴

- **クラウド小ファイルアクセスの高速化**: Box Drive上の大量の小ファイルを個別に読み書きする際のネットワーク遅延を回避。ZIP単位でローカルに取得・全展開し、ローカルSSD上で処理を完結させます。
- **透過的なアクセス**: ZIPファイル内のパスを、通常のフォルダのように扱うことができます（例: `archive.zip/data/file.txt`）。
- **安全な読み取り専用（既定 `mode="r"`）**: 解析目的の処理が元ZIPを誤って書き換えないよう、変更操作（書き込み・削除・移動）を呼び出し時点で確実にブロック（`ZipReadOnlyError`）。
- **明示的なトランザクション（`commit` / `rollback` / `edit`）**: 変更の保存・破棄を利用者が制御。コンテキストマネージャー（`with z.edit(...)`）に対応し、処理途中で例外が発生しても元ZIPを一切破壊しません。
- **更新競合検知 & データ保護**: ロード後に元ZIPが外部で変更された場合の競合検知（`ZipConflictError`）や、保存失敗時の編集データ保護（`ZipSaveError.recovery_path`）を完備。
- **日本語ダメ文字（CP932/0x5C）対応**: Windowsで作成されたShift-JISのZIPファイル（「表」「能」など）も文字化けせずに完全復元。
- **空ディレクトリ保持 & Zip Slip防御**: 空ディレクトリを欠落させず、悪意ある相対パストラバーサルを自動遮断。
- **外部ライブラリ連携**: `resolve()` により、Polars, Pillow, xlwings など「実際のファイルパス」を必要とするライブラリとシームレスに連携。

---

## インストール

```bash
uv add git+https://github.com/Nafania-family/z-lib-tool.git
```

---

## クイックスタート

### 1. 読み取り（解析用途・既定）

既定の `mode="r"` では、元ZIPの破壊や不要なクラウド同期は一切発生しません。

```python
from z_lib import Z_Lib

z = Z_Lib()

# 1. Box Drive上のZIPをマウント (ローカルに安全取得・展開)
z.load_zip("path/to/box_drive/dataset.zip")

# 2. 透過的に読み取り
with z.open("path/to/box_drive/dataset.zip/meta.json", "r", encoding="utf-8") as fp:
    print(fp.read())

# 3. 透過的な os / shutil 操作
for root, dirs, files in z.os.walk("path/to/box_drive/dataset.zip"):
    print(f"{root}: {len(files)} files")

# 4. 作業領域の安全な解放
z.close("path/to/box_drive/dataset.zip")
```

### 2. 安全な編集（トランザクション）

#### コンテキストマネージャーを使う場合（推奨）
ブロックを正常に抜けた場合のみ元ZIPへアトミックに書き戻されます。例外発生時は自動的にロールバックされ、元ZIPは保護されます。

```python
with z.edit("path/to/box_drive/dataset.zip"):
    with z.open("path/to/box_drive/dataset.zip/output.txt", "w", encoding="utf-8") as fp:
        fp.write("processed result")
    # ここで例外が起きても、元ZIPは一切書き換わりません
```

#### 明示的に commit / rollback を呼ぶ場合

```python
z.load_zip("dataset.zip", mode="rw")

with z.open("dataset.zip/config.ini", "w") as fp:
    fp.write("key=value")

# 編集内容を破棄して初期状態に戻す
z.rollback("dataset.zip")

# 編集を確定して元ZIPへアトミック書き戻し
# z.commit("dataset.zip")

z.close("dataset.zip")
```

---

## 高度な利用例

### 外部ライブラリ連携 (Polars, Pillow など)

展開先の一時実パスを渡すことで、外部プロセスやC拡張ライブラリからも直接扱えます。

```python
import polars as pl
from PIL import Image

real_csv_path = z.resolve("dataset.zip/table.csv")
df = pl.read_csv(real_csv_path)

with z.open("dataset.zip/image.png", "rb") as fp:
    img = Image.open(fp)
    img.show()
```

### 作業領域（高速SSD等）のカスタム設定

大容量ZIPや大量ファイルの展開先として、NVMe SSD等の高速ストレージを明示的に指定できます。

```python
z = Z_Lib(workspace_dir="D:/fast_nvme_temp")
```

### `swap_zip`: ロード状態の宣言的同期

現在のロード状態を指定リストの状態と差分同期させます。同じZIPの不要な再展開を防ぎます。

```python
# target.zip のみをロードし、それ以外を自動クローズ
z.swap_zip(["path/to/target.zip"])
```

### `load_nest`: フォルダ配下の全ZIP一括ロード

フォルダ内のすべての `.zip` ファイルを再帰探索して読み取り専用でロードします。

```python
z.load_nest("path/to/box_drive/monthly_reports/")
```

---

## エラーハンドリング

| 例外クラス | 発生条件 |
|---|---|
| `ZipReadOnlyError` | `mode="r"` のZIPに対して書き込み・削除・作成を試みた場合 |
| `ZipConflictError` | ロード後に外部（別端末やプロセス）で元ZIPが更新・削除されていた場合 |
| `ZipSaveError` | 再圧縮・検証・書き戻しに失敗した場合。`error.recovery_path` で未保存データを救出可能 |
| `ZipSecurityError` | `../` など展開先外への脱出を試みる不正なパスを検出した場合 |
| `ZipNotLoadedError` | マウントされていないZIP内部のパスにアクセスした場合 |

---

## ライセンス

MIT
