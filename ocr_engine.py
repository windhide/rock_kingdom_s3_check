from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)


class OCREngine:
    def __init__(self) -> None:
        self._engine: Any = None

    @property
    def ready(self) -> bool:
        return self._engine is not None

    def initialize(self) -> bool:
        if self._engine is not None:
            return True
        try:
            # Limit ONNX Runtime threads to reduce CPU
            import os
            os.environ.setdefault("OMP_NUM_THREADS", "2")
            os.environ.setdefault("MKL_NUM_THREADS", "2")

            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR(
                text_det_thresh=0.3,
                text_det_box_thresh=0.3,
                use_angle_cls=False,   # game text is always horizontal
                use_text_det=True,
                text_score=0.5,
            )
            logger.info("RapidOCR initialized")
            return True
        except Exception as exc:
            logger.error("Failed to initialize RapidOCR: %s", exc)
            return False

    def _preprocess(self, img: Image.Image) -> np.ndarray:
        """Prepare image for OCR: downscale, grayscale, contrast-stretch, denoise."""
        w, h = img.size

        # Downscale large images to save CPU
        max_dim = 480
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

        if img.mode != "L":
            img = img.convert("L")

        # Stretch contrast to full range
        arr = np.array(img, dtype=np.uint8)
        p2, p98 = np.percentile(arr, (2, 98))
        if p98 > p2:
            arr = np.clip((arr - p2) * 255.0 / (p98 - p2), 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

        # Light sharpen + denoise
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.MedianFilter(3))

        return np.array(img)

    def _ocr_image(self, arr: np.ndarray) -> str:
        result, _ = self._engine(arr)
        if result is None:
            return ""
        texts = [item[1] for item in result if item[1] and item[1].strip()]
        return " ".join(texts)

    def recognize(self, img: Image.Image) -> str:
        """Return all recognized text."""
        if not self.ready:
            return ""
        try:
            return self._ocr_image(self._preprocess(img))
        except Exception:
            return ""

    def recognize_batch(self, images: dict[str, Image.Image]) -> dict[str, str]:
        return {key: self.recognize(img) for key, img in images.items()}
