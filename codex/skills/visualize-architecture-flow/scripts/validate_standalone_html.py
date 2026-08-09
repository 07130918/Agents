#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="単一HTMLの自己完結性と基本的な教材UI要件を検証する",
    )
    parser.add_argument("html", type=Path, help="検証対象のHTMLファイル")
    return parser.parse_args()


def matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) is not None


def validate(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not path.is_file():
        return [f"ファイルが存在しません: {path}"], warnings
    if path.suffix.lower() != ".html":
        errors.append("拡張子が.htmlではありません")

    text = path.read_text(encoding="utf-8")

    required = {
        "DOCTYPE宣言": r"<!doctype\s+html",
        "言語指定": r"<html[^>]+lang=[\"'][^\"']+[\"']",
        "文字コード指定": r"<meta[^>]+charset=",
        "viewport指定": r"<meta[^>]+name=[\"']viewport[\"']",
        "インラインCSS": r"<style(?:\s|>)",
        "インラインJavaScript": r"<script(?:\s|>)",
    }
    for label, pattern in required.items():
        if not matches(pattern, text):
            errors.append(f"{label}がありません")

    forbidden = {
        "外部JavaScript": r"<script[^>]+src=",
        "外部stylesheet": r"<link[^>]+rel=[\"']stylesheet[\"']",
        "外部画像": r"<img[^>]+src=[\"']https?://",
        "CSSの外部URL": r"url\(\s*[\"']?https?://",
        "CSSの外部import": r"@import\s+(?:url\()?\s*[\"']?https?://",
        "iframe": r"<iframe(?:\s|>)",
        "未解決TODO": r"\bTODO\b|\[TODO[:\]]",
        "全角カッコ": r"[\uff08\uff09]",
    }
    for label, pattern in forbidden.items():
        if matches(pattern, text):
            errors.append(f"禁止要素を検出しました: {label}")

    recommended = {
        "reduced motion対応": r"prefers-reduced-motion",
        "ARIA live region": r"aria-live=",
        "SVG図": r"<svg(?:\s|>)",
        "再生操作": r"<(?:button)[^>]*>[^<]*(?:再生|一時停止|Play|Pause)",
    }
    for label, pattern in recommended.items():
        if not matches(pattern, text):
            warnings.append(f"推奨要素が見つかりません: {label}")

    return errors, warnings


def main() -> int:
    args = parse_args()
    errors, warnings = validate(args.html.expanduser().resolve())

    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"FAIL: errors={len(errors)}, warnings={len(warnings)}")
        return 1

    print(f"PASS: errors=0, warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
