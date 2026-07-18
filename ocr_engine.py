from __future__ import annotations

import logging
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

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
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR(
                text_det_thresh=0.3,
                text_det_box_thresh=0.3,
            )
            logger.info("RapidOCR initialized")
            return True
        except Exception as exc:
            logger.error("Failed to initialize RapidOCR: %s", exc)
            return False

    def _preprocess(self, img: Image.Image, invert: bool = False) -> np.ndarray:
        """Prepare image for OCR: upscale, grayscale, contrast-stretch, denoise."""
        w, h = img.size

        # Upscale small text regions
        scale = 1
        if h < 40:
            scale = 3
        elif h < 70:
            scale = 2
        if scale > 1:
            img = img.resize((w * scale, h * scale), Image.LANCZOS)

        if img.mode != "L":
            img = img.convert("L")

        # Stretch contrast to full range
        arr = np.array(img, dtype=np.uint8)
        p2, p98 = np.percentile(arr, (2, 98))
        if p98 > p2:
            arr = np.clip((arr - p2) * 255.0 / (p98 - p2), 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

        # Light sharpen
        img = img.filter(ImageFilter.SHARPEN)

        # Denoise
        img = img.filter(ImageFilter.MedianFilter(3))

        if invert:
            img = ImageOps.invert(img)

        return np.array(img)

    def _ocr_image(self, arr: np.ndarray) -> str:
        result, _ = self._engine(arr)
        if result is None:
            return ""
        texts = [item[1] for item in result if item[1] and item[1].strip()]
        return " ".join(texts)

    def recognize(self, img: Image.Image) -> str:
        """Return all recognized text, trying both normal and inverted."""
        if not self.ready:
            return ""
        try:
            # Try normal first
            text = self._ocr_image(self._preprocess(img, invert=False))
            if text.strip():
                return text
            # Fallback: try inverted (light text on dark bg)
            return self._ocr_image(self._preprocess(img, invert=True))
        except Exception:
            return ""

    def recognize_batch(self, images: dict[str, Image.Image]) -> dict[str, str]:
        return {key: self.recognize(img) for key, img in images.items()}
