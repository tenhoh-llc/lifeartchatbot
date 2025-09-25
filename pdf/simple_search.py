"""
シンプルな検索モジュール
READMEの仕様通り、PDFの該当ページ抜粋+出典を返す
"""
from dataclasses import dataclass
from typing import List, Optional
import sqlite3
from pathlib import Path
from rapidfuzz import fuzz
import re
from loguru import logger


@dataclass
class SearchResult:
    """検索結果"""
    file_name: str
    file_path: str
    page_no: int
    score: float
    text: str
    section: Optional[str]


def simple_search(
    query: str,
    index_path: Path = Path("./data/index.sqlite"),
    top_k: int = 5
) -> List[SearchResult]:
    """
    シンプルな検索を実行
    rapidfuzzによる部分一致のみ使用
    
    Args:
        query: 検索クエリ
        index_path: インデックスDBのパス
        top_k: 返す結果の最大数
        
    Returns:
        検索結果のリスト（スコア順）
    """
    if not query or not index_path.exists():
        return []
    
    # クエリの正規化（小文字化、空白除去）
    query_normalized = query.lower().strip()
    
    results = []
    
    with sqlite3.connect(index_path) as db:
        cursor = db.execute(
            "SELECT file_name, file_path, page_no, text, section FROM pages"
        )
        
        for file_name, file_path, page_no, text, section in cursor:
            # rapidfuzzによる部分一致スコア計算
            score = fuzz.partial_ratio(query_normalized, text.lower())
            
            # トピック固有のボーナス
            # 育休関連の質問は育児介護休業規程を優先
            if "育休" in query_normalized or "育児休" in query_normalized:
                if "育児介護" in file_name:
                    score += 30  # 育児介護休業規程にボーナス
                elif "パート" in file_name:
                    score -= 10  # パートタイマー規程にペナルティ
            
            # セクションマッチでボーナス
            if section and query_normalized in section.lower():
                score += 20
            
            # 最低スコア閾値
            if score >= 40:
                results.append(SearchResult(
                    file_name=file_name,
                    file_path=file_path,
                    page_no=page_no,
                    score=score,
                    text=text,
                    section=section
                ))
    
    # スコアでソート
    results.sort(key=lambda x: x.score, reverse=True)
    
    return results[:top_k]


def extract_snippet(text: str, query: str, window: int = 150) -> str:
    """
    テキストから該当箇所の抜粋を生成
    
    Args:
        text: 元のテキスト
        query: 検索クエリ
        window: 前後の文字数
        
    Returns:
        抜粋テキスト
    """
    text_lower = text.lower()
    query_lower = query.lower()
    
    # クエリの位置を探す
    pos = text_lower.find(query_lower)
    
    if pos == -1:
        # 見つからない場合は先頭から
        excerpt = text[:window * 2]
        if len(text) > window * 2:
            excerpt += "..."
        return excerpt
    
    # 前後の範囲を切り出し
    start = max(0, pos - window)
    end = min(len(text), pos + len(query) + window)
    
    excerpt = text[start:end]
    
    # 前後に省略記号を追加
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."
    
    # クエリをハイライト（Markdown太字）
    excerpt = excerpt.replace(query, f"**{query}**")
    
    return excerpt