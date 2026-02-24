# Z_Lib

ZIPファイルとローカルファイルを透過的に扱うためのPythonライブラリです。
標準の `os` や `shutil` ライブラリに近いインターフェースを提供し、ZIPファイルを一時ディレクトリにマウントすることで、パフォーマンスを犠牲にすることなく読み書きを容易にします。

## 特徴

- **透過的なアクセス**: ZIPファイル内のパスを、通常のフォルダのように扱うことができます（例: `archive.zip/data/file.txt`）。
- **絶対・相対パスの両立**: ZIPファイルを相対パスでロードしても絶対パスでアクセスでき、その逆も可能です。ライブラリ内部でパスを自動的に正規化・解決します。
- **明示的なステート管理**: ZIPファイルを `load` している間だけ実体化し、`unload` 時に一括で再圧縮・保存します。これにより、頻繁な解凍・圧縮操作を避け、高速なランダムアクセスを可能にします。
- **外部ライブラリ連携**: `open()` や `resolve()` メソッドにより、Pillow, Polars, Pandas などの「実際のファイルパス」や「ファイルオブジェクト」を必要とするライブラリとシームレスに連携できます。
- **マルチプロセス対応**: `resolve()` で取得した物理パスをワーカープロセスに渡すことで、並列処理も安全に行えます。

## インストール

```bash
uv add git+https://github.com/H-Nafania/z-lib-tool.git
```

## 使い方

### 基本フロー

```python
from z_lib import Z_Lib

# インスタンス作成
z = Z_Lib()

# 1. ZIPファイルをロード（mode="rw" で書き込み可能に）
z.load_zip("data.zip", mode="rw")

# 2. ファイルを読み込む
with z.open("data.zip/hello.txt", "r") as f:
    print(f.read())

# 3. アンロード（変更があれば元ファイルに反映される）
z.unload_zip("data.zip")
```

### 透過的な OS / Shutil 操作

`z.os` および `z.shutil` を使用すると、既存のコードを最小限の変更でZIP対応させることができます。

```python
# ファイル一覧の取得
files = z.os.listdir("data.zip/images")

# フォルダ作成
z.os.makedirs("data.zip/new_folder", exist_ok=True)

# ディレクトリの再帰探索 (仮想パスを返します)
for root, dirs, files in z.os.walk("data.zip"):
    print(f"Directory: {root}")
    for f in files:
        print(f"  File: {f}")

# ファイルコピー (ZIP内、またはZIP↔ローカル間)
z.shutil.copy2("data.zip/source.txt", "data.zip/backup.txt")
z.shutil.copy2("local_config.yaml", "data.zip/config.yaml")

# ファイル削除
z.os.remove("data.zip/temp.tmp")
```

### 外部ライブラリとの連携 (Pillow, Polars 等)

物理的なパスやファイルハンドルが必要な場合も簡単です。

```python
from PIL import Image
import polars as pl

# open() を使う (ファイルオブジェクトを渡す)
with z.open("data.zip/photo.jpg", "rb") as f:
    img = Image.open(f)
    img.show()

# resolve() を使う (一時展開された物理パスを取得)
# Polarsなどの外部プロセスやライブラリにパスを直接渡せます
real_path = z.resolve("data.zip/data.csv")
df = pl.read_csv(real_path)
```

### 高度な機能

#### `swap_zip`: ロード状態の宣言的同期

現在のロード状態をターゲットのリストと同期させます。不要なものはアンロードし、不足しているものだけをロードします。

```python
# zip1 をアンロードし、zip2, zip3 をロードする（差分のみ処理）
z.swap_zip(["zip2.zip", "zip3.zip"])
```

#### `load_nest`: フォルダ内のZIPを一括読込

指定したフォルダを再帰的に探索し、見つかったすべてのZIPファイルを読み取り専用でロードします。

```python
# 解析用ディレクトリ内の全ZIPをマウント
z.load_nest("path/to/archive_folder")
```

## 仕様と制限

- **自動クリーンアップ**: プログラム終了時にロード中のZIPは自動的に `unload`（保存）されます。
- **読み取り専用モード**: `mode="r"` (デフォルト) でロードした場合、ZIP内への変更はアンロード時に破棄されます。
- **一時ディレクトリ**: 展開先はOSのデフォルトの一時ディレクトリ（`/tmp` や `%TEMP%`）です。

## ライセンス

MIT
