import shutil
import argparse
from pathlib import Path


def remove_pycache(root_dir: str, dry_run: bool = False) -> None:
    root = Path(root_dir)

    if not root.exists():
        print(f"Không tồn tại: {root}")
        return

    if not root.is_dir():
        print(f"Không phải thư mục: {root}")
        return

    pycache_dirs = [p for p in root.rglob("__pycache__") if p.is_dir()]

    if not pycache_dirs:
        print("Không tìm thấy folder __pycache__ nào.")
        return

    print("Các folder __pycache__ tìm thấy:")
    for d in pycache_dirs:
        print(f" - {d}")

    if dry_run:
        print(f"\nDry run: sẽ xóa {len(pycache_dirs)} folder __pycache__.")
        return

    deleted_count = 0
    for d in pycache_dirs:
        try:
            shutil.rmtree(d)
            print(f"Đã xóa: {d}")
            deleted_count += 1
        except Exception as e:
            print(f"Lỗi khi xóa {d}: {e}")

    print(f"\nHoàn tất. Đã xóa {deleted_count} folder __pycache__.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Xóa toàn bộ folder __pycache__ trong một thư mục cha."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Đường dẫn thư mục cha. Mặc định là thư mục hiện tại.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ liệt kê các folder sẽ bị xóa, không xóa thật.",
    )

    args = parser.parse_args()
    remove_pycache(args.path, dry_run=args.dry_run)