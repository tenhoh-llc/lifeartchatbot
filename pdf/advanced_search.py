"""
高度な検索アルゴリズム
クエリ解析結果を活用して精度の高い検索を実現
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
import sqlite3
from pathlib import Path
from rapidfuzz import fuzz, process
import re
from loguru import logger
from core.query_analyzer import QueryIntent


@dataclass
class SearchResult:
    """検索結果を表すクラス"""
    file_name: str
    page_no: int
    score: float
    text: str
    section: Optional[str]
    matched_keywords: List[str]  # マッチしたキーワード
    relevance_reason: str  # なぜこの結果が関連するか


class AdvancedSearchEngine:
    """高度な検索エンジン"""
    
    def __init__(self, index_path: Path):
        """
        初期化
        
        Args:
            index_path: インデックスDBのパス
        """
        self.index_path = index_path
        self._build_cache()
    
    def _build_cache(self):
        """検索用のキャッシュを構築"""
        self.page_cache = []
        
        try:
            with sqlite3.connect(self.index_path) as db:
                cursor = db.execute(
                    "SELECT file_name, page_no, text, section FROM pages"
                )
                for row in cursor:
                    self.page_cache.append({
                        'file_name': row[0],
                        'page_no': row[1],
                        'text': row[2],
                        'section': row[3]
                    })
            logger.info(f"Cache built with {len(self.page_cache)} pages")
        except Exception as e:
            logger.error(f"Failed to build cache: {e}")
            self.page_cache = []
    
    def search(self, query_intent: QueryIntent, top_k: int = 5) -> List[SearchResult]:
        """
        クエリ意図に基づいて高度な検索を実行
        
        Args:
            query_intent: クエリ解析結果
            top_k: 返す結果の最大数
            
        Returns:
            検索結果のリスト
        """
        if not self.page_cache:
            logger.warning("No pages in cache")
            return []
        
        # 各ページをスコアリング
        scored_pages = []
        for page in self.page_cache:
            score, matched_keywords, reason = self._score_page(
                page, query_intent
            )
            if score > 0:
                scored_pages.append({
                    'page': page,
                    'score': score,
                    'matched_keywords': matched_keywords,
                    'reason': reason
                })
        
        # スコアでソート
        scored_pages.sort(key=lambda x: x['score'], reverse=True)
        
        # 結果を構築
        results = []
        for item in scored_pages[:top_k]:
            page = item['page']
            results.append(SearchResult(
                file_name=page['file_name'],
                page_no=page['page_no'],
                score=item['score'],
                text=page['text'],
                section=page['section'],
                matched_keywords=item['matched_keywords'],
                relevance_reason=item['reason']
            ))
        
        logger.info(f"Search found {len(results)} results for query: {query_intent.original_query}")
        return results
    
    def _score_page(self, page: dict, query_intent: QueryIntent) -> Tuple[float, List[str], str]:
        """
        ページをスコアリング
        
        Args:
            page: ページデータ
            query_intent: クエリ意図
            
        Returns:
            (スコア, マッチしたキーワード, 関連理由)
        """
        text = page['text']
        section = page['section'] or ""
        text_lower = text.lower()
        section_lower = section.lower()
        
        score = 0.0
        matched_keywords = []
        reasons = []
        
        # 1. キーワードマッチング（最重要）
        for keyword in query_intent.keywords:
            keyword_lower = keyword.lower()
            
            # 完全一致
            if keyword_lower in text_lower:
                score += 30
                matched_keywords.append(keyword)
                reasons.append(f"「{keyword}」が含まれる")
            
            # 部分一致（ファジーマッチ）
            else:
                ratio = fuzz.partial_ratio(keyword_lower, text_lower)
                if ratio > 80:
                    score += ratio * 0.2
                    matched_keywords.append(f"{keyword}(類似)")
                    reasons.append(f"「{keyword}」に類似")
        
        # 2. 同義語マッチング
        for keyword, synonyms in query_intent.synonyms.items():
            for synonym in synonyms:
                synonym_lower = synonym.lower()
                if synonym_lower in text_lower:
                    score += 20
                    matched_keywords.append(f"{synonym}({keyword}の同義語)")
                    reasons.append(f"「{keyword}」の関連語「{synonym}」")
                    break  # 同義語は1つマッチすれば十分
        
        # 3. セクションマッチング
        for keyword in query_intent.keywords:
            if keyword.lower() in section_lower:
                score += 15
                reasons.append(f"セクション「{section}」に該当")
        
        # 4. クエリタイプに応じた追加スコアリング
        score_boost, type_reason = self._score_by_query_type(
            text, query_intent.query_type
        )
        score += score_boost
        if type_reason:
            reasons.append(type_reason)
        
        # 5. コンテキストキーワードマッチング（補助的）
        for ctx_keyword in query_intent.context_keywords:
            if ctx_keyword.lower() in text_lower:
                score += 5
                reasons.append(f"文脈キーワード「{ctx_keyword}」")
        
        # 6. 文字列の近接度ボーナス
        # 複数のキーワードが近くに出現する場合
        if len(matched_keywords) >= 2:
            proximity_bonus = self._calculate_proximity_bonus(
                text, query_intent.keywords
            )
            score += proximity_bonus
            if proximity_bonus > 0:
                reasons.append("キーワードが近接して出現")
        
        # 理由を結合
        reason = "、".join(reasons[:3]) if reasons else "部分的な一致"
        
        return score, matched_keywords, reason
    
    def _score_by_query_type(self, text: str, query_type: str) -> Tuple[float, str]:
        """
        クエリタイプに応じた追加スコアリング
        
        Args:
            text: ページテキスト
            query_type: クエリタイプ
            
        Returns:
            (追加スコア, 理由)
        """
        text_lower = text.lower()
        
        if query_type == "条件":
            # 条件を示すパターンを探す
            patterns = ["場合", "とき", "際", "については", "に関して"]
            for pattern in patterns:
                if pattern in text_lower:
                    return 10, "条件説明を含む"
        
        elif query_type == "手続き":
            # 手続きを示すパターン
            patterns = ["手順", "方法", "申請", "提出", "必要書類"]
            for pattern in patterns:
                if pattern in text_lower:
                    return 10, "手続き説明を含む"
        
        elif query_type == "期限":
            # 期限を示すパターン
            patterns = ["まで", "以内", "期限", "締切", "日前", "日後"]
            for pattern in patterns:
                if pattern in text_lower:
                    return 10, "期限情報を含む"
        
        elif query_type == "金額":
            # 金額を示すパターン
            if re.search(r'\d+[円万千]', text):
                return 10, "金額情報を含む"
        
        return 0, ""
    
    def _calculate_proximity_bonus(self, text: str, keywords: List[str], window: int = 50) -> float:
        """
        キーワードの近接度ボーナスを計算
        
        Args:
            text: テキスト
            keywords: キーワードリスト
            window: 近接と見なす文字数
            
        Returns:
            ボーナススコア
        """
        if len(keywords) < 2:
            return 0
        
        text_lower = text.lower()
        positions = {}
        
        # 各キーワードの位置を取得
        for keyword in keywords[:3]:  # 最大3つまで
            keyword_lower = keyword.lower()
            pos = text_lower.find(keyword_lower)
            if pos >= 0:
                positions[keyword] = pos
        
        if len(positions) < 2:
            return 0
        
        # 位置の差を計算
        pos_values = list(positions.values())
        min_distance = min(
            abs(pos_values[i] - pos_values[j])
            for i in range(len(pos_values))
            for j in range(i + 1, len(pos_values))
        )
        
        # 近ければ近いほど高スコア
        if min_distance <= window:
            return max(0, 20 - (min_distance / window * 10))
        
        return 0
    
    def reindex(self):
        """インデックスを再構築"""
        self._build_cache()


# 既存コードとの互換性のための関数
def smart_search(query: str, top_k: int = 5, index_path: Path = None, context: Optional[str] = None):
    """
    スマート検索関数（既存コードとの互換性用）
    
    Args:
        query: 検索クエリ
        top_k: 返す結果の最大数
        index_path: インデックスDBのパス
        context: 前の会話のコンテキスト
        
    Returns:
        SearchResultの互換形式のリスト
    """
    from core.query_analyzer import QueryAnalyzer
    
    if index_path is None or not index_path.exists():
        logger.warning("Index path not provided or does not exist")
        return []
    
    # エンジンとアナライザを初期化
    engine = AdvancedSearchEngine(index_path)
    analyzer = QueryAnalyzer()
    
    # コンテキストを設定
    context_list = [context] if context else None
    
    # クエリを解析
    query_intent = analyzer.analyze(query, context_list)
    
    # 検索実行
    results = engine.search(query_intent, top_k)
    
    # 既存コードとの互換性のため、必要なフィールドを追加
    from dataclasses import dataclass
    
    @dataclass
    class SearchHit:
        """既存コードとの互換性用クラス"""
        file_name: str
        file_path: str
        page_no: int
        score: float
        text: str
        section: Optional[str]
    
    # 互換形式に変換
    hits = []
    for result in results:
        hit = SearchHit(
            file_name=result.file_name,
            file_path=f"data/pdfs/{result.file_name}",  # パスを推定
            page_no=result.page_no,
            score=result.score,
            text=result.text,
            section=result.section
        )
        hits.append(hit)
    
    return hits