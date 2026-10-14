"""Restore the exact monthly CSV from the repository's transport gzip."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def export_receipt(folder, filename):
    receipt = json.loads((folder / "public_export_packaging.json").read_text())
    if filename == receipt["uncompressed_filename"]:
        return receipt
    for extra in receipt.get("additional_exports", []):
        if filename == extra["uncompressed_filename"]:
            return extra
    raise ValueError(f"Unknown packaged export: {filename}")


def read_raw(folder, filename="monthly_paths.csv"):
    receipt = export_receipt(folder, filename)
    if "parts" in receipt:
        pieces = []
        for part in receipt["parts"]:
            data = (folder / part["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != part["sha256"]:
                raise ValueError(f"Export part hash mismatch: {part['path']}")
            pieces.append(data)
        compressed = b"".join(pieces)
    else:
        compressed = (folder / receipt["gzip_filename"]).read_bytes()
    if hashlib.sha256(compressed).hexdigest() != receipt["compressed_sha256"]:
        raise ValueError("Compressed export hash mismatch")
    raw = gzip.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != receipt["uncompressed_sha256"]:
        raise ValueError("Uncompressed export hash mismatch")
    return raw


def restore(folder, filename="monthly_paths.csv"):
    receipt = export_receipt(folder, filename)
    raw = read_raw(folder, filename)
    target = folder / receipt["uncompressed_filename"]
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("Refusing to overwrite a different local export")
    target.write_bytes(raw)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "results_theory_lab")
    args = parser.parse_args()
    receipt = json.loads((args.output / "public_export_packaging.json").read_text())
    names = [receipt["uncompressed_filename"]] + [r["uncompressed_filename"] for r in receipt.get("additional_exports", [])]
    for name in names:
        print(restore(args.output, name))
