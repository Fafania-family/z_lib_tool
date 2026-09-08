"""
Z_Lib I/O ベンチマークスクリプト
Box Drive等の同期ストレージを想定し、大量小ファイルを含むZIPに対する
各フェーズ（コピー、展開、読み取り、再圧縮、書き戻し）の所要時間を計測する。
"""

import argparse
import os
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def create_mock_zip(target_zip_path: Path, file_count: int, file_size_bytes: int = 1024) -> None:
    content = b"x" * file_size_bytes
    with zipfile.ZipFile(target_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(file_count):
            dir_index = i // 100
            arcname = f"dir_{dir_index:04d}/file_{i:06d}.txt"
            zf.writestr(arcname, content)


def run_benchmark(file_count: int, file_size_bytes: int = 1024) -> dict[str, float]:
    results: dict[str, float] = {}

    with tempfile.TemporaryDirectory(prefix="z_lib_bench_remote_") as remote_dir, \
         tempfile.TemporaryDirectory(prefix="z_lib_bench_local_") as local_dir:

        remote_path = Path(remote_dir)
        local_path = Path(local_dir)
        source_zip = remote_path / "mock_dataset.zip"

        print(f"Creating mock ZIP with {file_count} files ({file_size_bytes} bytes each)...")
        create_mock_zip(source_zip, file_count, file_size_bytes)
        zip_size_mb = source_zip.stat().st_size / (1024 * 1024)
        print(f"Mock ZIP created: {zip_size_mb:.2f} MB")

        # Phase 1: リモートからローカルへのコピー
        t0 = time.perf_counter()
        local_copy_zip = local_path / "dataset_copy.zip"
        shutil.copy2(source_zip, local_copy_zip)
        results["1_copy_remote_to_local"] = time.perf_counter() - t0

        # Phase 2: ローカルでの全展開
        t0 = time.perf_counter()
        extract_dir = local_path / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(local_copy_zip, "r") as zf:
            zf.extractall(extract_dir)
        results["2_local_extract_all"] = time.perf_counter() - t0

        # Phase 3: 全ファイル走査・個別読み込み
        t0 = time.perf_counter()
        read_count = 0
        total_bytes_read = 0
        for root, _, files in os.walk(extract_dir):
            for f in files:
                p = Path(root) / f
                with open(p, "rb") as fp:
                    data = fp.read()
                    total_bytes_read += len(data)
                read_count += 1
        results["3_full_read_local"] = time.perf_counter() - t0

        # Phase 4: ファイル追記・編集（10%のファイルを更新）
        t0 = time.perf_counter()
        modified_count = 0
        for root, _, files in os.walk(extract_dir):
            for f in files:
                if modified_count >= (file_count // 10):
                    break
                p = Path(root) / f
                with open(p, "ab") as fp:
                    fp.write(b"\nappended_content")
                modified_count += 1
        results["4_edit_files"] = time.perf_counter() - t0

        # Phase 5: ローカル再圧縮
        t0 = time.perf_counter()
        recompressed_zip = local_path / "recompressed.zip"
        with zipfile.ZipFile(recompressed_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(extract_dir):
                for d in dirs:
                    dir_path = Path(root) / d
                    arcname = str(dir_path.relative_to(extract_dir)).replace("\\", "/") + "/"
                    zf.writestr(arcname, b"")
                for f in files:
                    file_path = Path(root) / f
                    arcname = str(file_path.relative_to(extract_dir)).replace("\\", "/")
                    zf.write(file_path, arcname)
        results["5_recompress_local"] = time.perf_counter() - t0

        # Phase 6: ZIP検証 (testzip)
        t0 = time.perf_counter()
        with zipfile.ZipFile(recompressed_zip, "r") as zf:
            corrupt = zf.testzip()
            if corrupt is not None:
                raise RuntimeError(f"Corrupted entry found: {corrupt}")
        results["6_verify_zip"] = time.perf_counter() - t0

        # Phase 7: リモートへのアトミック書き戻し
        t0 = time.perf_counter()
        temp_remote_dst = source_zip.with_suffix(".tmp_write")
        shutil.copy2(recompressed_zip, temp_remote_dst)
        os.replace(temp_remote_dst, source_zip)
        results["7_atomic_write_back"] = time.perf_counter() - t0

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Z_Lib I/O Benchmark")
    parser.add_argument("--count", type=int, default=1000, help="Number of files to generate in ZIP")
    parser.add_argument("--size", type=int, default=1024, help="Size of each file in bytes")
    args = parser.parse_args()

    results = run_benchmark(args.count, args.size)

    print("\n### ベンチマーク結果 (ファイル数: {}, 1ファイルサイズ: {} bytes)".format(args.count, args.size))
    print("| 処理フェーズ | 所要時間 (秒) | 割合 (%) |")
    print("|---|---|---|")

    total_time = sum(results.values())
    for phase, sec in results.items():
        ratio = (sec / total_time * 100) if total_time > 0 else 0
        print(f"| `{phase}` | {sec:.4f} s | {ratio:.1f} % |")
    print(f"| **合計** | **{total_time:.4f} s** | **100.0 %** |\n")


if __name__ == "__main__":
    main()
