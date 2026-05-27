# PDF / 文書処理パターン (Python)

PDF・画像からの抽出処理で繰り返し使うパターンと落とし穴をまとめる。プロジェクト固有設定は `CLAUDE.md` 優先。

## ツール選定マトリクス

| やりたいこと | 推奨 | 補足 |
|---|---|---|
| プレーンテキスト抽出 (テキスト PDF) | `pypdf` / `PyMuPDF` (fitz) | fitz の方が高速・崩れが少ない |
| テーブル抽出 | `pdfplumber` | 罫線あり PDF に強い |
| レイアウト保持・座標取得 | `PyMuPDF` (`page.get_text("dict")`) | ブロック・行・spans 単位で取れる |
| スキャン PDF / 画像 OCR (OSS) | `pdf2image` + `pytesseract` | 日本語は `lang="jpn"` |
| 高精度 OCR (商用) | Google Vision / Azure Document Intelligence | 帳票・複雑レイアウトはこちら |
| PDF → 画像 | `pdf2image` (poppler 必須) | `dpi=300` 以上を推奨 |
| ページ分割・結合 | `pypdf` | シンプル操作のみ |

❌ `PyPDF2` は古い名前。新規は `pypdf` を使う

---

## まず最初にやる: テキスト PDF か スキャン PDF かの判定

```python
import fitz  # PyMuPDF

def is_text_pdf(path: str, sample_pages: int = 3) -> bool:
    """先頭数ページのテキスト量で判定。OCR が必要かを早期に決める"""
    doc = fitz.open(path)
    total_chars = 0
    for i in range(min(sample_pages, len(doc))):
        total_chars += len(doc[i].get_text("text").strip())
    doc.close()
    return total_chars > 100  # 経験的閾値
```

判定を最初に入れないと、OCR が必要な PDF に対して `pdfplumber` が空文字を返し続けて気付かないバグになる。

---

## テキスト抽出 (PyMuPDF)

```python
import fitz

def extract_text(path: str) -> list[str]:
    """ページごとのテキストを返す"""
    doc = fitz.open(path)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return pages

def extract_with_layout(path: str) -> list[dict]:
    """ブロック・座標付きで抽出 (帳票で行列対応が必要なとき)"""
    doc = fitz.open(path)
    result = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        result.append(blocks)
    doc.close()
    return result
```

**落とし穴**:
- 縦書き PDF は文字順がおかしくなる。`page.get_text("text", sort=True)` でも厳しい場合は **座標から並べ替え** が必要
- フッタ・ヘッダが本文に混ざる。**Y 座標でフィルタ** するか、ページごとに上下 N% を除外

---

## テーブル抽出 (pdfplumber)

```python
import pdfplumber

def extract_tables(path: str) -> list[list[list[str]]]:
    """ページ × テーブル × 行 × 列"""
    with pdfplumber.open(path) as pdf:
        return [page.extract_tables() for page in pdf.pages]

# カスタム設定 (罫線が薄い PDF 向け)
table_settings = {
    "vertical_strategy": "lines",      # or "text"
    "horizontal_strategy": "lines",
    "intersection_tolerance": 5,
}
with pdfplumber.open(path) as pdf:
    tables = pdf.pages[0].extract_tables(table_settings)
```

**落とし穴**:
- 結合セル (rowspan/colspan) は **同じ値が複数セルに展開** されることもあれば **None が入る** こともある。後処理で正規化必須
- 罫線のない表は `strategy="text"` でテキスト位置から推定。失敗率は上がる
- 表の前後にあるキャプションは取れない。`extract_text` と併用

---

## OCR (Tesseract)

```python
from pdf2image import convert_from_path
import pytesseract

def ocr_pdf(path: str, lang: str = "jpn", dpi: int = 300) -> list[str]:
    images = convert_from_path(path, dpi=dpi)
    return [pytesseract.image_to_string(img, lang=lang) for img in images]
```

**インストール**:
- macOS: `brew install poppler tesseract tesseract-lang`
- `tesseract-lang` で日本語データ (`jpn.traineddata`) が入る

**精度を上げる前処理**:
```python
from PIL import Image, ImageOps

def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    img = img.convert("L")                   # グレースケール
    img = ImageOps.autocontrast(img)         # コントラスト調整
    # 必要なら二値化: img = img.point(lambda x: 0 if x < 128 else 255, "1")
    return img
```

---

## 商用 OCR (高精度が必要なとき)

```python
# Google Vision (Document AI)
from google.cloud import vision
client = vision.ImageAnnotatorClient()
with open(image_path, "rb") as f:
    image = vision.Image(content=f.read())
response = client.document_text_detection(image=image, image_context={"language_hints": ["ja"]})
text = response.full_text_annotation.text
```

商用が必要な場面の目安:
- ✅ 帳票・請求書など **テーブル + 手書き混在**
- ✅ 解像度の低いスキャン (300 dpi 未満)
- ✅ 多言語混在
- ❌ きれいなテキスト PDF → そもそも OCR 不要

---

## LLM 前処理パイプライン

PDF を Claude/GPT に渡す前の典型的な流れ:

```python
def pdf_to_llm_chunks(path: str, max_chars: int = 8000) -> list[dict]:
    """LLM 渡し用のチャンク化。各チャンクにメタデータを残す"""
    pages = extract_text(path)
    chunks = []
    for page_num, text in enumerate(pages, start=1):
        text = normalize_whitespace(text)
        for chunk in split_by_chars(text, max_chars):
            chunks.append({"page": page_num, "text": chunk, "source": path})
    return chunks

def normalize_whitespace(text: str) -> str:
    import re
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def split_by_chars(text: str, max_chars: int) -> list[str]:
    """段落境界で分割。境界が見つからなければ強制カット"""
    out, current = [], ""
    for para in text.split("\n\n"):
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                out.append(current)
            current = para if len(para) <= max_chars else para[:max_chars]
    if current:
        out.append(current)
    return out
```

**重要**:
- ✅ **ページ番号を必ず保持**。LLM の回答に「ページ X 参照」と書かせるため
- ✅ チャンク間は **オーバーラップを 200-500 字** 持たせると境界またぎの文脈が壊れにくい
- ❌ 改行・空白の正規化を後回しにすると、同じ内容でも token 数が膨れる

---

## チェックリスト (PDF 処理を実装するとき)

- [ ] テキスト PDF / スキャン PDF の判定を入れた
- [ ] テーブルがある場合 `pdfplumber` の strategy を試行錯誤した
- [ ] OCR の前処理 (グレースケール・コントラスト) を入れた
- [ ] 日本語縦書き・回転ページの可能性を確認した
- [ ] フッタ・ヘッダ・ページ番号の除去ロジックを入れた
- [ ] LLM に渡すなら チャンク化 + ページ番号メタデータを保持した
- [ ] 失敗時のフォールバック (テキスト抽出 → OCR) を用意した
