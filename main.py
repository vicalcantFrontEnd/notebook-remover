"""
NotebookLM Watermark Remover - Entry point.
"""

import sys


def check_dependencies():
    """Verify required packages are available."""
    missing = []
    try:
        import cv2  # noqa: F401
    except ImportError:
        missing.append("opencv-python")
    try:
        import numpy  # noqa: F401
    except ImportError:
        missing.append("numpy")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow")

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print(f"Install them with:  pip install {' '.join(missing)}")
        sys.exit(1)


def main():
    check_dependencies()

    from watermark_remover import _find_ffmpeg
    try:
        _find_ffmpeg()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    from gui import WatermarkRemoverApp
    app = WatermarkRemoverApp()
    app.run()


if __name__ == "__main__":
    main()
