"""判断是否需要重新生成 UI / 资源代码，用于加速启动。

Start.bat 每次启动都会调用 convert_ui_to_py.bat，原先会无条件执行
`pyside6-uic` 与 `pyside6-rcc`，导致 13MB 的 media_rc.py 被反复重写、
其 .pyc 字节码缓存每次失效。这里用"源文件内容哈希 + PySide6 版本"作为签名，
没有变化就让转换脚本跳过生成。

用法：
    python ui_build_check.py           # 无需重建返回 0，需要重建返回 1
    python ui_build_check.py --stamp   # 生成完成后写入本次签名
"""
import hashlib
import sys
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent
UI_FILE = CORE_DIR / "MainWindow.ui"
QRC_FILE = CORE_DIR / "media.qrc"
PY_FILE = CORE_DIR / "main_window.py"
RCC_PY_FILE = CORE_DIR / "media_rc.py"
STAMP_FILE = CORE_DIR / ".ui_build_stamp"


def build_signature():
    """根据源文件内容与 PySide6 版本计算签名；源文件缺失时返回 None。"""
    digest = hashlib.md5()
    for src in (UI_FILE, QRC_FILE):
        if not src.is_file():
            return None
        digest.update(src.read_bytes())
    try:
        import PySide6
        digest.update(PySide6.__version__.encode("utf-8"))
    except Exception:
        digest.update(b"unknown")
    return digest.hexdigest()


def main():
    signature = build_signature()
    if signature is None:
        print("[ui_build_check] 源文件缺失，需要生成")
        return 1

    if "--stamp" in sys.argv:
        STAMP_FILE.write_text(signature, encoding="utf-8")
        return 0

    if not (PY_FILE.is_file() and RCC_PY_FILE.is_file()):
        print("[ui_build_check] 生成产物缺失，需要生成")
        return 1

    previous = STAMP_FILE.read_text(encoding="utf-8").strip() if STAMP_FILE.is_file() else ""
    if previous == signature:
        print("[ui_build_check] UI 与资源无变化，跳过生成")
        return 0

    print("[ui_build_check] UI 或 PySide6 版本已变化，重新生成")
    return 1


if __name__ == "__main__":
    sys.exit(main())
