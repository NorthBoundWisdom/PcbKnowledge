"""Pinned local PDF.js distribution contract for evidence review."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping


PDFJS_VERSION = "6.2.108"
PDFJS_BUILD = "legacy"
PDFJS_PACKAGE = "pdfjs-dist"
PDFJS_PACKAGE_INTEGRITY = (
    "sha512-YxFb+SQcodN2rnX9Tn3dHYlqfb7NjlzzfONPpJd+AKoKtUjEdevTfbC07d5Tcczz"
    "OK6261auRkP/M8OBHs9vFQ=="
)
PDFJS_PACKAGE_SHASUM = "1e0ce0f4b3a034f953dbbe2334ab01fbddf0eb30"
PDFJS_STATIC_RELATIVE = Path("vendor") / "pdfjs" / PDFJS_VERSION
PDFJS_RUNTIME_FILES: Mapping[str, tuple[int, str]] = {
    "LICENSE": (
        10174,
        "0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594",
    ),
    "pdf.min.mjs": (
        512483,
        "9fab0c910bf1484835c5c2aeb68f7eb3dfce7f9eb435a004526c5af86d70890c",
    ),
    "pdf.worker.min.mjs": (
        1312452,
        "bc0d1b88ea0b66196b1d36a58ac243c6d92adfe725624e2a9fdd381bdf8ef434",
    ),
}


class PdfJsVendorError(RuntimeError):
    """The committed PDF.js snapshot does not match its pinned contract."""


@dataclass(frozen=True, slots=True)
class PdfJsVendorReceipt:
    root: Path
    version: str
    build: str
    file_count: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _expected_manifest() -> dict[str, object]:
    return {
        "build": PDFJS_BUILD,
        "files": {
            name: {"byte_size": byte_size, "sha256": digest}
            for name, (byte_size, digest) in PDFJS_RUNTIME_FILES.items()
        },
        "package": PDFJS_PACKAGE,
        "package_integrity": PDFJS_PACKAGE_INTEGRITY,
        "package_shasum": PDFJS_PACKAGE_SHASUM,
        "registry": "https://registry.npmjs.org",
        "version": PDFJS_VERSION,
    }


def default_pdfjs_vendor_root() -> Path:
    return Path(__file__).with_name("static") / PDFJS_STATIC_RELATIVE


def validate_pdfjs_vendor(vendor_root: Path | None = None) -> PdfJsVendorReceipt:
    """Validate the exact vendored PDF.js bytes and supply-chain manifest."""

    root = (default_pdfjs_vendor_root() if vendor_root is None else vendor_root).resolve()
    if root.is_symlink() or not root.is_dir():
        raise PdfJsVendorError(f"PDF.js vendor directory is missing or unsafe: {root}")

    expected_names = {*PDFJS_RUNTIME_FILES, "vendor-manifest.json"}
    actual_names = {path.name for path in root.iterdir()}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        detail = f"missing={missing} extra={extra}"
        raise PdfJsVendorError(f"PDF.js vendor file set changed: {detail}")

    manifest_path = root / "vendor-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PdfJsVendorError("PDF.js vendor manifest is missing or unsafe")
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PdfJsVendorError("PDF.js vendor manifest is invalid") from error
    expected_manifest = _expected_manifest()
    if manifest != expected_manifest:
        raise PdfJsVendorError("PDF.js vendor manifest does not match the pinned contract")
    canonical = json.dumps(expected_manifest, indent=2, sort_keys=True) + "\n"
    if manifest_text != canonical:
        raise PdfJsVendorError("PDF.js vendor manifest is not canonical JSON")

    for name, (expected_size, expected_digest) in PDFJS_RUNTIME_FILES.items():
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise PdfJsVendorError(f"PDF.js vendor file is missing or unsafe: {name}")
        if path.stat().st_size != expected_size:
            raise PdfJsVendorError(f"PDF.js vendor byte size changed: {name}")
        if _sha256(path) != expected_digest:
            raise PdfJsVendorError(f"PDF.js vendor SHA-256 changed: {name}")

    for name in ("pdf.min.mjs", "pdf.worker.min.mjs"):
        if PDFJS_VERSION.encode("ascii") not in (root / name).read_bytes():
            raise PdfJsVendorError(f"PDF.js bundle does not declare {PDFJS_VERSION}: {name}")

    return PdfJsVendorReceipt(
        root=root,
        version=PDFJS_VERSION,
        build=PDFJS_BUILD,
        file_count=len(PDFJS_RUNTIME_FILES),
    )
