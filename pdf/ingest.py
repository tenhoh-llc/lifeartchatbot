"""
PDF取り込みモジュール
PDFファイルからテキストを抽出してデータベースに保存
"""
import fitz  # pymupdf
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import re
from loguru import logger


@dataclass
class PageRecord:
    """
    PDFページ1枚分のデータを保持するクラス
    
    データクラスを使用することで:
    - 自動的に__init__メソッドが生成される
    - 型ヒントが明確になる
    - イミュータブルにすることも可能
    """
    file_name: str      # PDFファイル名
    file_path: str      # PDFファイルのフルパス
    page_no: int        # ページ番号（1から開始）
    text: str           # 抽出されたテキスト
    section: Optional[str]  # セクション名（条文番号など）


def clean_text(text: str) -> str:
    """
    抽出したテキストをクリーニング
    
    Args:
        text: 生のテキスト
    
    Returns:
        クリーニング済みテキスト
    
    処理内容:
    - 連続する空白を1つに統一
    - 不要な改行を削除
    - 全角スペースを半角に変換
    """
    if not text:
        return ""
    
    # 全角スペースを半角に変換
    text = text.replace("\u3000", " ")
    
    # 連続する空白を1つに
    text = re.sub(r"\s+", " ", text)
    
    # 行頭行末の空白を削除
    text = text.strip()
    
    # ページ番号などの定型文を削除（例: "- 1 -", "Page 1"）
    text = re.sub(r"^[-\s]*\d+[-\s]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^Page\s+\d+$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    
    return text


def extract_section(text: str) -> Optional[str]:
    """
    テキストからセクション情報を抽出
    
    Args:
        text: ページのテキスト
    
    Returns:
        セクション名（見つからない場合はNone）
    
    抽出パターン:
    - 第○条
    - 第○章
    - ○.○.○ 形式の見出し
    """
    if not text:
        return None
    
    # 最初の100文字程度から抽出
    sample = text[:200] if len(text) > 200 else text
    
    # パターンマッチング
    patterns = [
        r"第[一二三四五六七八九十\d]+条",  # 第○条
        r"第[一二三四五六七八九十\d]+章",  # 第○章
        r"第[一二三四五六七八九十\d]+節",  # 第○節
        r"\d+\.\s+[\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+",  # 1. 見出し
        r"\d+\.\d+\s+[\w\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+",  # 1.1 見出し
    ]
    
    for pattern in patterns:
        match = re.search(pattern, sample)
        if match:
            return match.group(0).strip()
    
    return None


def extract_pages(pdf_path: Path) -> List[PageRecord]:
    """
    PDFファイルからページごとにテキストを抽出
    
    Args:
        pdf_path: PDFファイルのパス
    
    Returns:
        ページレコードのリスト
    
    PyMuPDFの特徴:
    - 高速な処理
    - 日本語対応
    - レイアウト情報の取得も可能
    """
    pages = []
    
    try:
        # PDFファイルを開く
        doc = fitz.open(pdf_path)
        logger.info(f"Processing PDF: {pdf_path.name} ({doc.page_count} pages)")
        
        for page_num, page in enumerate(doc, start=1):
            try:
                # テキストを抽出
                text = page.get_text("text")
                
                # テキストをクリーニング
                text = clean_text(text)
                
                # 空のページはスキップ
                if not text or len(text) < 10:
                    logger.debug(f"Skipping empty page {page_num}")
                    continue
                
                # セクション情報を抽出
                section = extract_section(text)
                
                # ページレコードを作成
                record = PageRecord(
                    file_name=pdf_path.name,
                    file_path=str(pdf_path.absolute()),
                    page_no=page_num,
                    text=text,
                    section=section
                )
                
                pages.append(record)
                
                if section:
                    logger.debug(f"Page {page_num}: Found section '{section}'")
                
            except Exception as e:
                logger.error(f"Failed to extract page {page_num}: {e}")
                continue
        
        doc.close()
        logger.info(f"Extracted {len(pages)} pages from {pdf_path.name}")
        
    except Exception as e:
        logger.error(f"Failed to open PDF {pdf_path}: {e}")
        # フォールバック: pdfminer.sixを試す
        try:
            pages = extract_pages_fallback(pdf_path)
        except Exception as fallback_error:
            logger.error(f"Fallback extraction also failed: {fallback_error}")
            pages = []
    
    return pages


def extract_pages_fallback(pdf_path: Path) -> List[PageRecord]:
    """
    フォールバック: pdfminer.sixを使用した抽出
    PyMuPDFで失敗した場合に使用
    """
    from pdfminer.high_level import extract_text_to_fp
    from pdfminer.layout import LAParams
    from io import StringIO
    
    pages = []
    
    try:
        # PDFからテキストを抽出
        output = StringIO()
        with open(pdf_path, 'rb') as fp:
            extract_text_to_fp(
                fp, 
                output,
                laparams=LAParams(),
                output_type='text',
                codec='utf-8'
            )
        
        # 全テキストを取得
        full_text = output.getvalue()
        
        # ページ区切りで分割（簡易的な処理）
        # 実際のページ境界は不明なので、一定の文字数で分割
        chunk_size = 3000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        
        for i, chunk in enumerate(chunks, start=1):
            text = clean_text(chunk)
            if text:
                record = PageRecord(
                    file_name=pdf_path.name,
                    file_path=str(pdf_path.absolute()),
                    page_no=i,
                    text=text,
                    section=extract_section(text)
                )
                pages.append(record)
        
        logger.info(f"Fallback extraction: {len(pages)} chunks from {pdf_path.name}")
        
    except Exception as e:
        logger.error(f"Fallback extraction failed: {e}")
    
    return pages


def extract_text_file(txt_path: Path) -> List[PageRecord]:
    """
    テキストファイルからページごとにテキストを抽出
    
    Args:
        txt_path: テキストファイルのパス
    
    Returns:
        ページレコードのリスト
    """
    pages = []
    
    try:
        # テキストファイルを読み込み
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"Processing text file: {txt_path.name}")
        
        # テキストをクリーニング
        content = clean_text(content)
        
        # 空のファイルはスキップ
        if not content or len(content) < 10:
            logger.debug("Skipping empty text file")
            return pages
        
        # セクション情報を抽出
        section = extract_section(content)
        
        # ページレコードを作成（テキストファイルは1ページとして扱う）
        record = PageRecord(
            file_name=txt_path.name,
            file_path=str(txt_path.absolute()),
            page_no=1,
            text=content,
            section=section
        )
        
        pages.append(record)
        
        if section:
            logger.debug(f"Found section '{section}' in text file")
        
        logger.info(f"Extracted 1 page from {txt_path.name}")
        
    except Exception as e:
        logger.error(f"Failed to process text file {txt_path}: {e}")
    
    return pages


def ingest_directory(pdf_dir: Path, index_path: Path, include_docx: bool = True) -> int:
    """
    ディレクトリ内の全PDF・テキストファイルを処理してインデックスに登録
    
    Args:
        pdf_dir: PDFファイルが格納されたディレクトリ
        index_path: SQLiteデータベースのパス
    
    Returns:
        登録されたページ数
    
    処理フロー:
    1. PDFファイルとテキストファイルを列挙
    2. 各ファイルからテキストを抽出
    3. データベースに保存
    """
    from .index import upsert_pages
    
    if not pdf_dir.exists():
        logger.error(f"Directory does not exist: {pdf_dir}")
        return 0
    
    # PDFファイルとテキストファイルを列挙
    pdf_files = list(pdf_dir.glob("*.pdf"))
    txt_files = list(pdf_dir.glob("*.txt"))
    
    all_files = pdf_files + txt_files
    
    if not all_files:
        logger.warning(f"No PDF or text files found in {pdf_dir}")
        return 0
    
    logger.info(f"Found {len(pdf_files)} PDF files and {len(txt_files)} text files to process")
    
    # 全ページを収集
    all_pages = []
    
    # PDFファイルを処理
    for pdf_path in sorted(pdf_files):
        pages = extract_pages(pdf_path)
        all_pages.extend(pages)
    
    # テキストファイルを処理
    for txt_path in sorted(txt_files):
        pages = extract_text_file(txt_path)
        all_pages.extend(pages)
    
    # .docxファイルも処理（オプション）
    if include_docx:
        try:
            from .doc_reader import extract_docx_text
            docx_files = list(pdf_dir.glob("*.docx"))
            
            if docx_files:
                logger.info(f"Found {len(docx_files)} .docx files to process")
                
            for docx_path in sorted(docx_files):
                docx_pages = extract_docx_text(docx_path)
                # DocPageRecordをPageRecordに変換
                for dp in docx_pages:
                    all_pages.append(PageRecord(
                        file_name=dp.file_name,
                        file_path=dp.file_path,
                        page_no=dp.page_no,
                        text=dp.text,
                        section=dp.section
                    ))
        except ImportError:
            if list(pdf_dir.glob("*.docx")):
                logger.warning("Found .docx files but python-docx not installed")
                logger.info("Install with: pip install python-docx")
    
    # データベースに保存
    if all_pages:
        upsert_pages(index_path, all_pages)
        logger.info(f"Indexed {len(all_pages)} pages total")
    else:
        logger.warning("No pages extracted from any file")
    
    return len(all_pages)


if __name__ == "__main__":
    # コマンドライン実行用
    from pathlib import Path
    import sys
    
    if len(sys.argv) > 1:
        pdf_dir = Path(sys.argv[1])
    else:
        pdf_dir = Path("./data/pdfs")
    
    index_path = Path("./data/index.sqlite")
    
    # ログ設定
    from core.logging import setup_logging
    setup_logging()
    
    # インデックス作成
    count = ingest_directory(pdf_dir, index_path)
    print(f"Indexed {count} pages")