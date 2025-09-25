"""
Word文書（.doc, .docx）を読み込むモジュール
Dropboxから直接ダウンロードも可能
"""
import os
from pathlib import Path
from typing import List, Optional
import requests
from dataclasses import dataclass
from loguru import logger

# python-docxのインストールが必要: pip install python-docx
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not installed. Install with: pip install python-docx")


@dataclass
class DocPageRecord:
    """Word文書のページレコード"""
    file_name: str
    file_path: str
    page_no: int
    text: str
    section: Optional[str]


def extract_docx_text(docx_path: Path) -> List[DocPageRecord]:
    """
    .docxファイルからテキストを抽出
    
    Args:
        docx_path: .docxファイルのパス
    
    Returns:
        ページレコードのリスト
    """
    if not DOCX_AVAILABLE:
        logger.error("python-docx is not installed")
        return []
    
    try:
        doc = Document(docx_path)
        pages = []
        
        # 段落ごとに処理（Wordにはページ概念がないため段落で分割）
        current_text = []
        current_section = None
        page_no = 1
        
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            
            if not text:
                continue
            
            # 見出しスタイルをセクションとして検出
            if paragraph.style.name.startswith('Heading'):
                # 新しいセクションの開始
                if current_text:
                    # 前のセクションを保存
                    pages.append(DocPageRecord(
                        file_name=docx_path.name,
                        file_path=str(docx_path),
                        page_no=page_no,
                        text='\n'.join(current_text),
                        section=current_section
                    ))
                    page_no += 1
                    current_text = []
                
                current_section = text
                current_text.append(text)
            else:
                current_text.append(text)
            
            # 一定量のテキストでページ分割（約1000文字）
            if len('\n'.join(current_text)) > 1000:
                pages.append(DocPageRecord(
                    file_name=docx_path.name,
                    file_path=str(docx_path),
                    page_no=page_no,
                    text='\n'.join(current_text),
                    section=current_section
                ))
                page_no += 1
                current_text = []
        
        # 残りのテキストを保存
        if current_text:
            pages.append(DocPageRecord(
                file_name=docx_path.name,
                file_path=str(docx_path),
                page_no=page_no,
                text='\n'.join(current_text),
                section=current_section
            ))
        
        logger.info(f"Extracted {len(pages)} sections from {docx_path.name}")
        return pages
        
    except Exception as e:
        logger.error(f"Failed to extract from {docx_path}: {e}")
        return []


def download_from_dropbox(dropbox_url: str, save_path: Path) -> bool:
    """
    Dropboxから直接ファイルをダウンロード
    
    Args:
        dropbox_url: Dropbox共有リンク
        save_path: 保存先パス
    
    Returns:
        成功したらTrue
    
    使用例:
        url = "https://www.dropbox.com/s/xxxxx/document.docx?dl=0"
        download_from_dropbox(url, Path("data/pdfs/document.docx"))
    """
    try:
        # Dropboxの直接ダウンロードリンクに変換
        if dropbox_url.endswith('?dl=0'):
            dropbox_url = dropbox_url.replace('?dl=0', '?dl=1')
        elif not dropbox_url.endswith('?dl=1'):
            dropbox_url += '?dl=1'
        
        # ダウンロード
        response = requests.get(dropbox_url, stream=True)
        response.raise_for_status()
        
        # ファイル保存
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Downloaded file to {save_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to download from Dropbox: {e}")
        return False


def batch_download_dropbox(urls_file: Path, target_dir: Path):
    """
    複数のDropboxファイルを一括ダウンロード
    
    Args:
        urls_file: URLリストファイル（1行1URL）
        target_dir: ダウンロード先ディレクトリ
    
    使用例:
        # urls.txtに各行にDropboxリンクを記載
        batch_download_dropbox(Path("urls.txt"), Path("data/pdfs"))
    """
    if not urls_file.exists():
        logger.error(f"URLs file not found: {urls_file}")
        return
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    with open(urls_file, 'r') as f:
        urls = f.readlines()
    
    for url in urls:
        url = url.strip()
        if not url or url.startswith('#'):
            continue
        
        # ファイル名を抽出
        filename = url.split('/')[-1].split('?')[0]
        save_path = target_dir / filename
        
        logger.info(f"Downloading {filename}...")
        download_from_dropbox(url, save_path)


# 既存のingest.pyに統合するための関数
def process_all_documents(docs_dir: Path) -> List[tuple]:
    """
    .docx, .doc, .txt, .pdf すべてを処理
    
    Returns:
        (file_name, page_no, text, section) のタプルのリスト
    """
    all_pages = []
    
    # .docxファイルを処理
    for docx_file in docs_dir.glob("*.docx"):
        pages = extract_docx_text(docx_file)
        for page in pages:
            all_pages.append((
                page.file_name,
                page.page_no,
                page.text,
                page.section
            ))
    
    # .docファイル（古い形式）も処理したい場合
    for doc_file in docs_dir.glob("*.doc"):
        logger.warning(f"Old .doc format not supported directly: {doc_file.name}")
        logger.info("Please convert to .docx or .pdf format")
    
    return all_pages


if __name__ == "__main__":
    # 使用例
    
    # 1. Dropboxから単一ファイルをダウンロード
    # url = "https://www.dropbox.com/s/xxxxx/就業規則.docx?dl=0"
    # download_from_dropbox(url, Path("data/pdfs/就業規則.docx"))
    
    # 2. ローカルの.docxファイルを読み込み
    # pages = extract_docx_text(Path("data/pdfs/就業規則.docx"))
    # for page in pages:
    #     print(f"Page {page.page_no}: {page.text[:100]}...")
    
    print("Doc reader module ready")
    print("Install python-docx: pip install python-docx")
    print("For Dropbox: Create urls.txt with one URL per line")