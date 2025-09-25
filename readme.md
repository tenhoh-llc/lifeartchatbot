# 社内チャットボット 詳細設計（Claude Code向け）

> ターゲット: Claude Code / コーディングエージェントがこの設計だけで実装・テスト・Docker化・CI連携まで完了できること。

---

## 1. 目的・非目的・完成条件（DoD）

* **目的**: 社内規約PDF（就業規則・給与規程など）を参照し、質問に対して該当ページの抜粋（根拠付き）を返す**軽量チャットUI**を最短で提供。
* **非目的（今回スコープ外）**: 本格RAG、外部DB連携、ユーザー管理、多言語、権限分離、監査ログの長期保存。
* **DoD（金曜版）**:

  * `streamlit run app.py` で起動→**単一パスワード認証**→質問入力→**PDFの該当ページ抜粋**+出典（ファイル名・ページ番号）を返す。
  * 代表10クエリに対して“それらしい根拠付き回答”を継続的に返せる。
  * Lint/format/test がCIでパス。Dockerで同等動作。
  * README、.env.example、Makefile、（任意）Dockerfile、（任意）簡易アーキ図付与。

---

## 2. 技術スタック / ランタイム

* **Python 3.11**
* **Streamlit**: UI（チャット、出典パネル、簡易認証）
* **PDF抽出**: `pymupdf`（高速・レイアウト頑健）、フォールバックに `pdfminer.six`
* **検索/ランキング**: `rapidfuzz` による部分一致 + 簡易BM25相当（スコア重みづけ）
* **設定/バリデーション**: `pydantic`
* **ロギング**: `loguru`
* **ユニットテスト**: `pytest`
* **コード整形**: `black` + `ruff`
* **（任意）要約**: 任意のLLM API（OpenAI/Claude など）。抽出済みスニペットのみを要約対象。

---

## 3. 環境変数 / 設定

`.env.example`

```
APP_PASSWORD=change_me
PDF_DIR=./data/pdfs
INDEX_PATH=./data/index.sqlite
LOG_LEVEL=INFO
LLM_PROVIDER=none   # none|openai|anthropic
LLM_API_KEY=
TZ=Asia/Tokyo
```

`config.py`（pydantic）

* `AppConfig`:

  * `app_password: str`
  * `pdf_dir: Path`
  * `index_path: Path`
  * `log_level: Literal["DEBUG","INFO","WARNING","ERROR"]`
  * `llm_provider: Literal["none","openai","anthropic"]`
  * `llm_api_key: Optional[str]`

**エラー時の挙動**: 必須値が欠落→起動時例外（Streamlitに赤帯で表示）。

---

## 4. ディレクトリ構成

```
repo/
├─ app.py                       # Streamlitエントリ
├─ core/
│  ├─ config.py                 # pydantic設定
│  ├─ logging.py                # loguru設定
│  └─ auth.py                   # 単一パスワード認証
├─ pdf/
│  ├─ ingest.py                 # PDF → ページ単位抽出
│  ├─ index.py                  # SQLiteインデックスI/O
│  ├─ search.py                 # マッチング/スコアリング
│  └─ snippet.py                # 抜粋生成/ハイライト
├─ llm/
│  ├─ summarize.py              # （任意）抜粋の短文化
│  └─ prompts.py                # ルールベースのプロンプト
├─ ui/
│  ├─ layout.py                 # Streamlitパネル/コンポーネント
│  └─ styles.py                 # スタイル/テーマ
├─ tests/
│  ├─ test_pdf_extract.py
│  ├─ test_search.py
│  └─ test_snippet.py
├─ data/
│  ├─ pdfs/                     # PDF配置（.gitignore）
│  └─ index.sqlite              # 生成物（.gitignore）
├─ .github/workflows/ci.yml
├─ requirements.txt
├─ .env.example
├─ Makefile
├─ Dockerfile                   # 任意
└─ README.md
```

---

## 5. データモデル / SQLite スキーマ

`pdf/index.py` が管理。初回インデクス時に作成。

```sql
CREATE TABLE IF NOT EXISTS pages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  page_no INTEGER NOT NULL,
  text TEXT NOT NULL,
  section TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pages_file ON pages(file_name);
CREATE INDEX IF NOT EXISTS idx_pages_text ON pages(text);
```

**要件**

* ページ単位で1レコード。
* `section` は目次や大見出しが取れれば保存（無理ならNULL）。

---

## 6. PDF取り込み（ingest）

### フロー

1. `PDF_DIR`配下のPDF列挙
2. `pymupdf`でページ→テキスト抽出
3. ノイズ除去（連続空白、改行、ヘッダ/フッタの定型文の簡易削除）
4. `section` 推定（ページ先頭の大見出しや「第○条」パターンの正規表現）
5. SQLiteへUPSERT（同一`file_name`+`page_no`があれば更新）

### 関数シグネチャ

```python
# pdf/ingest.py
@dataclass
class PageRecord:
    file_name: str
    file_path: str
    page_no: int
    text: str
    section: str | None

def extract_pages(pdf_path: Path) -> list[PageRecord]: ...

def ingest_directory(pdf_dir: Path, index_path: Path) -> int: ...  # 戻り値: 登録件数
```

**受け入れ条件**

* 文字化け率が低い（全角が崩れない）。
* 1PDFのページ数と登録件数一致。

---

## 7. 検索/ランキング（search）

### 要件

* **RAGなし**。完全に抽出テキストに対する**部分一致/スコアリング**で上位候補を返す。
* 同義語/表記ゆれ対応のため、**簡易正規化**（全角半角、英数小文字化、句読点除去）を実施。

### 手法

* `rapidfuzz.fuzz.partial_ratio` を基本スコア（0-100）。
* 単語IDF近似で**キーワード出現重み**を加点（BM25簡略）。
* `section` ヒットで+α（条・章にマッチしたらブースト）。

### 関数

```python
# pdf/search.py
@dataclass
class SearchHit:
    file_name: str
    page_no: int
    score: float
    text: str
    section: str | None

def search(query: str, top_k: int = 5) -> list[SearchHit]: ...
```

**受け入れ条件**

* 代表10クエリで、上位5件中に妥当なページが概ね含まれる。

---

## 8. 抜粋/ハイライト（snippet）

### 仕様

* マッチ部分の**前後N文字（例: ±120字）**を抜粋し、三点リーダで前後を省略。
* マルチマッチ時は最良1〜2箇所を結合（最大合計300〜400字）。
* マークアップ: `**ヒット語**` で強調（StreamlitのMarkdownで表示）。

### 関数

```python
# pdf/snippet.py
@dataclass
class Snippet:
    excerpt: str     # 強調済みMarkdown
    start: int       # 文字インデックス（任意）
    end: int

def make_snippet(text: str, query: str, window: int = 120) -> Snippet: ...
```

**受け入れ条件**

* 抜粋が読みやすく、条文の意味が通る最小文脈を含む。

---

## 9. （任意）要約LLM

* **目的**: 抜粋済みテキストを**短文化**して要点を先頭に表示。
* **制約**: LLMは**抽出結果の意訳のみ**。追加の事実や推論は禁止。
* **プロンプト**（`llm/prompts.py`）:

```
あなたは社内規程の要点を短く整理するアシスタントです。
与えられた抜粋テキストのみを根拠に、最大120文字で結論を要約してください。
新しい事実や条文番号の創作は禁止。曖昧なら「該当箇所を確認してください」と返すこと。
---
抜粋:
{EXCERPT}
```

* **関数**: `summarize(excerpt: str, provider: str, api_key: str) -> str`

---

## 10. 認証/権限（auth）

* 単一パスワードのみ（`.env: APP_PASSWORD`）。
* Streamlitセッション状態に`authenticated: bool`を保持。
* 認証失敗3回で**一時ブロック（5分）**（セッション内カウンタ）。

---

## 11. UIレイアウト（Streamlit）

* **ヘッダ**: タイトル、バージョン、最終インデクス日時表示。
* **左カラム**: チャット履歴（ユーザー/システムの吹き出し）
* **中央カラム**: 入力欄 + 送信ボタン + 回答（上:要点/下:抜粋）
* **右カラム**: 出典カード（`ファイル名 / p.{page_no} / スコア`）と、（任意）ページ画像プレビュー（難しい場合は省略）
* **注意書き**: 「法的効力なし、原本確認を推奨」固定表示。

**擬似コード（app.py）**

```python
if not auth.check():
    ui.render_login()
    st.stop()

if ui.sidebar_reindex_clicked():
    with st.spinner("Reindexing..."):
        n = ingest_directory(cfg.pdf_dir, cfg.index_path)
        st.success(f"Indexed {n} pages")

q = ui.input_query()
if q:
    hits = search(q, top_k=5)
    if not hits:
        ui.render_nohit()
    else:
        best = hits[0]
        snip = make_snippet(best.text, q)
        summary = summarize_if_enabled(snip.excerpt)
        ui.render_answer(summary, snip, hits)
```

---

## 12. ロギング/監視

* `loguru`で`logs/app.log`へ出力。
* PII対策: 入力クエリは**前方16文字のみ**記録（残りは`…`）、応答本文は記録しない設定オプション。
* 重要イベント: 起動/認証成功・失敗/再インデクス/例外。

---

## 13. エラーハンドリング指針

* PDF抽出失敗: 該当ページをスキップし警告ログ。最終件数で気付けるようにする。
* 検索0件: UIでヒント（同義語、別表記、用語例）を提示。
* LLM API失敗: 要約無効でフォールバック（抜粋のみ表示）。

---

## 14. 性能要件（目安）

* PDF合計 5〜20MB / 100〜500ページ想定。
* 初回インデクス < 60秒（ローカル）。
* 検索→上位5件表示まで < 1.5秒。

---

## 15. セキュリティ/運用

* パスワードは共有管理台帳でローテ（最低月1）。
* Docker環境では `PDF_DIR` を**読み取り専用ボリューム**でマウント。
* 社内ネットワーク/HTTPSのLB越しで公開（別途インフラ側）。

---

## 16. CI（GitHub Actions）

`.github/workflows/ci.yml`

```yaml
name: ci
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: ruff check .
      - run: black --check .
      - run: pytest -q
```

---

## 17. Makefile

```
.PHONY: dev lint fmt test index

dev:
	streamlit run app.py

lint:
	ruff check .

fmt:
	black .

test:
	pytest -q

index:
	python -m pdf.ingest
```

---

## 18. requirements.txt（暫定）

```
streamlit==1.38.0
pydantic==2.8.2
python-dotenv==1.0.1
pymupdf==1.24.10
pdfminer.six==20240706
rapidfuzz==3.9.6
loguru==0.7.2
black==24.8.0
ruff==0.6.9
pytest==8.3.2
```

---

## 19. Dockerfile（任意）

```dockerfile
FROM python:3.11-slim
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 TZ=Asia/Tokyo
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## 20. 最小コードスケルトン（抜粋）

**core/config.py**

```python
from pydantic import BaseModel
from pathlib import Path
import os

class AppConfig(BaseModel):
    app_password: str
    pdf_dir: Path
    index_path: Path
    log_level: str = "INFO"
    llm_provider: str = "none"
    llm_api_key: str | None = None

    @classmethod
    def load(cls):
        from dotenv import load_dotenv
        load_dotenv()
        return cls(
            app_password=os.getenv("APP_PASSWORD", ""),
            pdf_dir=Path(os.getenv("PDF_DIR", "./data/pdfs")),
            index_path=Path(os.getenv("INDEX_PATH", "./data/index.sqlite")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            llm_provider=os.getenv("LLM_PROVIDER", "none"),
            llm_api_key=os.getenv("LLM_API_KEY"),
        )
```

**core/auth.py**

```python
import streamlit as st

def check(password_env: str) -> bool:
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
        st.session_state.fail = 0
    if st.session_state.auth_ok:
        return True
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if pwd == password_env:
            st.session_state.auth_ok = True
        else:
            st.session_state.fail += 1
            st.error("Invalid password")
    if st.session_state.fail >= 3:
        st.stop()
    return st.session_state.auth_ok
```

**pdf/ingest.py**（要点のみ）

```python
import fitz  # pymupdf
from dataclasses import dataclass
from pathlib import Path
from .index import upsert_pages

@dataclass
class PageRecord:
    file_name: str
    file_path: str
    page_no: int
    text: str
    section: str | None

def extract_pages(pdf_path: Path) -> list[PageRecord]:
    doc = fitz.open(pdf_path)
    out = []
    for i, page in enumerate(doc):
        txt = page.get_text("text")
        txt = "\n".join(line.strip() for line in txt.splitlines() if line.strip())
        section = None
        out.append(PageRecord(pdf_path.name, str(pdf_path), i+1, txt, section))
    return out

def ingest_directory(pdf_dir: Path, index_path: Path) -> int:
    all_pages = []
    for p in sorted(pdf_dir.glob("*.pdf")):
        all_pages.extend(extract_pages(p))
    upsert_pages(index_path, all_pages)
    return len(all_pages)
```

**pdf/index.py**（要点のみ）

```python
import sqlite3
from pathlib import Path
from typing import Iterable
from .ingest import PageRecord

def ensure_schema(db: sqlite3.Connection):
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS pages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          file_name TEXT NOT NULL,
          file_path TEXT NOT NULL,
          page_no INTEGER NOT NULL,
          text TEXT NOT NULL,
          section TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_pages_file ON pages(file_name);
        CREATE INDEX IF NOT EXISTS idx_pages_text ON pages(text);
        """
    )

def upsert_pages(index_path: Path, pages: Iterable[PageRecord]):
    with sqlite3.connect(index_path) as db:
        ensure_schema(db)
        cur = db.cursor()
        cur.execute("DELETE FROM pages")  # 単純化: 全再構築
        cur.executemany(
            "INSERT INTO pages(file_name,file_path,page_no,text,section) VALUES(?,?,?,?,?)",
            [(p.file_name, p.file_path, p.page_no, p.text, p.section) for p in pages],
        )
        db.commit()

def iter_pages(index_path: Path):
    with sqlite3.connect(index_path) as db:
        for row in db.execute("SELECT file_name,page_no,text,section FROM pages"):
            yield row
```

**pdf/search.py**（要点のみ）

```python
from dataclasses import dataclass
from rapidfuzz import fuzz
import sqlite3
from pathlib import Path

@dataclass
class SearchHit:
    file_name: str
    page_no: int
    score: float
    text: str
    section: str | None

def _norm(s: str) -> str:
    return s.lower()

def search(query: str, top_k: int = 5, index_path: Path | str = "./data/index.sqlite"):
    qn = _norm(query)
    hits: list[SearchHit] = []
    with sqlite3.connect(index_path) as db:
        for file_name, page_no, text, section in db.execute(
            "SELECT file_name,page_no,text,section FROM pages"
        ):
            score = fuzz.partial_ratio(qn, _norm(text))
            if section:
                score += 5 if qn in _norm(section) else 0
            if score > 0:
                hits.append(SearchHit(file_name, page_no, score, text, section))
    hits.sort(key=lambda x: x.score, reverse=True)
    return hits[:top_k]
```

**pdf/snippet.py**（要点のみ）

```python
from dataclasses import dataclass
import re

@dataclass
class Snippet:
    excerpt: str
    start: int
    end: int

def make_snippet(text: str, query: str, window: int = 120) -> Snippet:
    idx = text.lower().find(query.lower())
    if idx < 0:
        idx = 0
    start = max(0, idx - window)
    end = min(len(text), idx + len(query) + window)
    excerpt = text[start:end]
    excerpt = re.sub(re.escape(query), f"**{query}**", excerpt, flags=re.I)
    if start > 0:
        excerpt = "…" + excerpt
    if end < len(text):
        excerpt = excerpt + "…"
    return Snippet(excerpt, start, end)
```

**app.py**（要点のみ）

```python
import streamlit as st
from core.config import AppConfig
from core import auth
from pdf.ingest import ingest_directory
from pdf.search import search
from pdf.snippet import make_snippet

cfg = AppConfig.load()
st.set_page_config(page_title="社内AI QA", layout="wide")

st.title("社内チャットボット（PDF参照）")

if not auth.check(cfg.app_password):
    st.stop()

with st.sidebar:
    if st.button("インデクス再構築"):
        with st.spinner("Indexing..."):
            n = ingest_directory(cfg.pdf_dir, cfg.index_path)
            st.success(f"Indexed {n} pages")

q = st.text_input("質問を入力（例: 有休の繰越）")
if st.button("送信") and q:
    hits = search(q, top_k=5, index_path=cfg.index_path)
    if not hits:
        st.warning("該当が見つかりませんでした。キーワードを変えてお試しください。")
    else:
        best = hits[0]
        snip = make_snippet(best.text, q)
        st.subheader("要点（抜粋ベース）")
        st.write(snip.excerpt)
        st.caption(f"出典: {best.file_name} p.{best.page_no} / score={best.score:.1f}")
        with st.expander("候補（上位）"):
            for h in hits:
                st.write(f"{h.file_name} p.{h.page_no} score={h.score:.1f}")
```

---

## 21. テスト（pytest）

**tests/test_search.py**

```python
from pdf.snippet import make_snippet

def test_make_snippet_basic():
    txt = "これは有給休暇の繰越に関する条文です。翌年度に繰り越せます。"
    snip = make_snippet(txt, "繰越", window=5)
    assert "**繰越**" in snip.excerpt
```

---

## 22. 代表クエリ（検収用）

* 「有給休暇の繰越」
* 「給与の締日と支払日」
* 「時短勤務の申請条件」
* 「遅刻・早退の扱い」
* 「時間外勤務の上限」

---

## 23. 既知の制限・拡張余地

* 縦書き/画像PDFは抽出が不全→将来OCR（tesseract/rapidocr）を追加。
* 誤爆時にFAQ誘導を出す（`data/faq.yaml`を導入して候補提示）。
* 埋め込み類似度でランキング改善（**回答は常に抜粋根拠ベース**を維持）。

---

## 24. 受け渡し物チェックリスト

* [ ] README / 起動・インデクス手順
* [ ] .env.example
* [ ] requirements.txt
* [ ] Makefile
* [ ] CI（ruff/black/pytest）
* [ ] 最小テストケース
* [ ] （任意）Dockerfile
* [ ] コード一式（上記構成）

---

この設計に沿って実装すれば、Claude Codeは各ファイルを順に生成→テスト→起動確認→Docker化→CI連携まで自動化できます。

# 開発前提
- ユーザーは Python 初心者
- 今回のプロジェクトは Python フレームワークを利用
- すべてのコード解説は初心者が理解できるように「仕組みの解説つき」で提示すること