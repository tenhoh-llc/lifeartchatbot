"""
強化された検索モジュール
略語・同義語対応とクエリ拡張による精度向上
"""
from dataclasses import dataclass
from typing import List, Optional, Set, Dict
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
    matched_terms: List[str]  # マッチした用語


# 同義語・略語辞書
SYNONYM_DICT = {
    "育休": ["育児休業", "育児休暇"],
    "産休": ["産前産後休業", "産前産後休暇", "出産休暇"],
    "有休": ["有給休暇", "年次有給休暇", "有給"],
    "介護休": ["介護休業", "介護休暇"],
    "時短": ["短時間勤務", "時短勤務", "時間短縮"],
    "残業": ["時間外労働", "時間外勤務", "超過勤務"],
    "パート": ["パートタイマー", "パートタイム"],
}

# 逆引き辞書の生成
REVERSE_SYNONYM = {}
for short, longs in SYNONYM_DICT.items():
    for long_term in longs:
        REVERSE_SYNONYM[long_term] = short


def expand_query(query: str) -> Set[str]:
    """
    クエリを拡張（略語→正式名称、正式名称→略語）
    
    Args:
        query: 検索クエリ
        
    Returns:
        拡張されたクエリセット
    """
    expanded = {query}
    query_lower = query.lower()
    
    # 略語を正式名称に展開
    for short, longs in SYNONYM_DICT.items():
        if short in query_lower:
            for long_term in longs:
                expanded.add(query_lower.replace(short, long_term))
    
    # 正式名称を略語に変換
    for long_term, short in REVERSE_SYNONYM.items():
        if long_term in query_lower:
            expanded.add(query_lower.replace(long_term, short))
    
    return expanded


def calculate_smart_score(
    query: str,
    text: str,
    file_name: str,
    section: Optional[str]
) -> tuple[float, List[str]]:
    """
    スマートスコア計算（同義語対応）
    
    Returns:
        (スコア, マッチした用語のリスト)
    """
    text_lower = text.lower()
    query_lower = query.lower()
    
    # クエリ拡張
    expanded_queries = expand_query(query)
    
    # 最高スコアを計算
    max_score = 0
    matched_terms = []
    
    for exp_query in expanded_queries:
        # 部分一致スコア
        score = fuzz.partial_ratio(exp_query, text_lower)
        
        # 完全一致ボーナス
        if exp_query in text_lower:
            score += 30
            matched_terms.append(exp_query)
        
        # キーワードごとのマッチング
        keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', exp_query)
        for keyword in keywords:
            if len(keyword) >= 2 and keyword in text_lower:
                score += 10
                if keyword not in matched_terms:
                    matched_terms.append(keyword)
        
        max_score = max(max_score, score)
    
    # ファイル名によるボーナス/ペナルティ
    if "育" in query_lower or "育休" in query_lower:
        if "育児介護" in file_name:
            max_score += 40
        elif "パート" in file_name:
            max_score -= 20
    elif "パート" in query_lower:
        if "パート" in file_name:
            max_score += 40
        else:
            max_score -= 20
    
    # セクションマッチボーナス
    if section:
        for exp_query in expanded_queries:
            if exp_query in section.lower():
                max_score += 25
                break
    
    return max_score, matched_terms


def search_enhanced(
    query: str,
    index_path: Path = Path("./data/index.sqlite"),
    top_k: int = 5,
    min_score: int = 30
) -> List[SearchResult]:
    """
    強化された検索（同義語・略語対応）
    
    Args:
        query: 検索クエリ
        index_path: インデックスDBのパス
        top_k: 返す結果の最大数
        min_score: 最低スコア
        
    Returns:
        検索結果のリスト
    """
    if not query or not index_path.exists():
        return []
    
    results = []
    
    with sqlite3.connect(index_path) as db:
        cursor = db.execute(
            "SELECT file_name, file_path, page_no, text, section FROM pages"
        )
        
        for file_name, file_path, page_no, text, section in cursor:
            score, matched_terms = calculate_smart_score(
                query, text, file_name, section
            )
            
            if score >= min_score:
                results.append(SearchResult(
                    file_name=file_name,
                    file_path=file_path,
                    page_no=page_no,
                    score=score,
                    text=text,
                    section=section,
                    matched_terms=matched_terms
                ))
    
    # スコアでソート
    results.sort(key=lambda x: x.score, reverse=True)
    
    return results[:top_k]


def extract_smart_snippet(
    text: str,
    query: str,
    matched_terms: List[str],
    window: int = 150
) -> str:
    """
    スマート抜粋生成（マッチした用語をハイライト）
    
    Args:
        text: 元のテキスト
        query: 検索クエリ
        matched_terms: マッチした用語リスト
        window: 前後の文字数
        
    Returns:
        抜粋テキスト
    """
    text_lower = text.lower()
    
    # マッチした用語の位置を探す
    best_pos = -1
    best_term = query
    
    # まず拡張クエリでの位置を探す
    for term in matched_terms:
        pos = text_lower.find(term.lower())
        if pos != -1:
            best_pos = pos
            best_term = term
            break
    
    # 見つからない場合は元のクエリで
    if best_pos == -1:
        best_pos = text_lower.find(query.lower())
        best_term = query
    
    # それでも見つからない場合は先頭から
    if best_pos == -1:
        best_pos = 0
    
    # 抜粋範囲の計算
    start = max(0, best_pos - window)
    end = min(len(text), best_pos + len(best_term) + window)
    
    excerpt = text[start:end]
    
    # 前後に省略記号を追加
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."
    
    # すべてのマッチ用語をハイライト
    for term in matched_terms:
        # 大文字小文字を無視してマッチング
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        excerpt = pattern.sub(f"**{term}**", excerpt)
    
    return excerpt


# 旧API互換性のため
def generate_answer_from_hits(query: str, hits: List[SearchResult]) -> Dict:
    """
    検索結果から適切な回答を生成（旧API互換）
    """
    if not hits:
        return {
            "found": False,
            "answer": "該当する情報が見つかりませんでした。",
            "suggestions": [
                "より具体的なキーワードで検索してください",
                "育児休業に関しては「育休」「育児休業」などで検索",
                "パートタイマーに関しては「パート」「時給」などで検索"
            ]
        }
    
    best_hit = hits[0]
    
    # 回答の信頼度を判定
    confidence = "high" if best_hit.score >= 100 else "medium" if best_hit.score >= 70 else "low"
    
    # スニペット生成
    excerpt = extract_smart_snippet(
        best_hit.text,
        query,
        best_hit.matched_terms,
        window=200
    )
    
    return {
        "found": True,
        "answer": excerpt,
        "source": {
            "file": best_hit.file_name,
            "page": best_hit.page_no,
            "section": best_hit.section,
            "score": best_hit.score,
            "confidence": confidence
        },
        "all_results": [
            {
                "file": hit.file_name,
                "page": hit.page_no,
                "score": hit.score
            }
            for hit in hits
        ]
    }


# テスト用関数
def test_search():
    """検索機能のテスト"""
    test_queries = [
        "育休の条件は？",
        "有休の繰越",
        "パートの勤務時間",
        "育児休業の申請"
    ]
    
    for query in test_queries:
        print(f"\n検索: {query}")
        print(f"拡張: {expand_query(query)}")
        
        results = search_enhanced(query, top_k=3)
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result.file_name} - Page {result.page_no}")
            print(f"   Score: {result.score:.1f}")
            print(f"   Matched: {', '.join(result.matched_terms)}")
            snippet = extract_smart_snippet(
                result.text, query, result.matched_terms, window=100
            )
            print(f"   Excerpt: {snippet[:200]}...")


if __name__ == "__main__":
    test_search()