"""
インテリジェント検索モジュール
文脈理解と条文優先順位を考慮した高精度検索
"""
from dataclasses import dataclass
from typing import List, Optional, Set, Dict, Tuple
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
    matched_terms: List[str]
    relevance_type: str  # 関連性のタイプ（definition/condition/procedure等）


# 同義語・略語辞書
SYNONYM_DICT = {
    "育休": ["育児休業", "育児休暇"],
    "産休": ["産前産後休業", "産前産後休暇", "出産休暇"],
    "有休": ["有給休暇", "年次有給休暇"],
    "有給": ["有給休暇", "年次有給休暇", "有休"],  # 有給も追加
    "介護休": ["介護休業", "介護休暇"],
    "時短": ["短時間勤務", "時短勤務", "時間短縮"],
    "残業": ["時間外労働", "時間外勤務", "超過勤務"],
    "パート": ["パートタイマー", "パートタイム"],
}

# クエリ意図のパターン
INTENT_PATTERNS = {
    "definition": ["とは", "について", "教えて", "説明"],  # 定義・概要
    "condition": ["条件", "要件", "対象", "資格", "できる"],  # 条件・対象者
    "procedure": ["手続き", "申請", "方法", "やり方", "どうやって"],  # 手続き
    "period": ["期間", "いつまで", "何日", "何ヶ月", "何年"],  # 期間
    "benefit": ["給付", "手当", "給与", "お金", "支給"],  # 給付・手当
}

# 条文の重要度（若い番号ほど基本的な内容）
ARTICLE_IMPORTANCE = {
    "目的": 100,  # 第1条（目的）
    "定義": 95,   # 定義条項
    "対象": 90,   # 第2条（対象者）
    "条件": 85,   # 条件・要件
    "期間": 70,   # 期間
    "手続": 60,   # 手続き
    "申請": 60,   # 申請
    "給付": 50,   # 給付
}


def expand_query(query: str) -> Set[str]:
    """クエリを拡張（略語→正式名称）"""
    expanded = {query}
    query_lower = query.lower()
    
    # まず元のクエリで拡張
    for short, longs in SYNONYM_DICT.items():
        if short in query_lower:
            for long_term in longs:
                expanded.add(query_lower.replace(short, long_term))
    
    # キーワードのみでも拡張（「について教えて」などを除去）
    # 意図パターンを除去
    clean_query = query_lower
    for pattern_list in INTENT_PATTERNS.values():
        for pattern in pattern_list:
            clean_query = clean_query.replace(pattern, "").strip()
    clean_query = clean_query.replace("？", "").replace("?", "").strip()
    
    if clean_query != query_lower and clean_query:
        expanded.add(clean_query)
        # クリーンなクエリでも同義語展開
        for short, longs in SYNONYM_DICT.items():
            if short in clean_query:
                for long_term in longs:
                    expanded.add(clean_query.replace(short, long_term))
    
    return expanded


def analyze_query_intent(query: str) -> str:
    """
    クエリの意図を分析
    
    Returns:
        意図のタイプ（definition/condition/procedure/period/benefit/general）
    """
    query_lower = query.lower()
    
    for intent_type, keywords in INTENT_PATTERNS.items():
        if any(keyword in query_lower for keyword in keywords):
            return intent_type
    
    # 「について」「教えて」がよく使われるので、デフォルトは定義
    if "？" in query or "?" in query:
        return "definition"
    
    return "general"


def extract_article_info(text: str) -> Tuple[Optional[int], str]:
    """
    テキストから条文番号と種類を抽出
    
    Returns:
        (条文番号, 条文タイプ)
    """
    # より広範囲で第○条のパターンを探す
    article_patterns = [
        r'第([０-９0-9]{1,3})条',  # 数字（全角・半角）
        r'第([一二三四五六七八九十]{1,3})条',  # 漢数字
    ]
    
    article_num = None
    # テキスト全体を探索（ただし最初の1000文字まで）
    search_text = text[:1000]
    
    for pattern in article_patterns:
        matches = re.findall(pattern, search_text)
        if matches:
            article_str = matches[0]
            
            # 条文番号を数値に変換（拡張版）
            article_num_map = {
                '１': 1, '２': 2, '３': 3, '４': 4, '５': 5,
                '６': 6, '７': 7, '８': 8, '９': 9, '１０': 10,
                '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
                '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
                '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
                '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            }
            
            # 2桁以上の数字の処理
            if article_str.isdigit():
                article_num = int(article_str)
            else:
                article_num = article_num_map.get(article_str, None)
                
                # 30番台、40番台などの処理
                if article_num is None and len(article_str) >= 2:
                    try:
                        article_num = int(article_str)
                    except:
                        article_num = 99  # デフォルト値
            
            if article_num:
                break
    
    # 条文のタイプを判定
    text_preview = search_text.lower()
    article_type = "general"
    
    # キーワードベースでタイプを判定
    if '目的' in text_preview[:200]:
        article_type = "目的"
    elif '年次有給休暇' in text_preview or '有給休暇' in text_preview:
        article_type = "休暇"  # 有給休暇関連
    elif '育児休業' in text_preview or '介護休業' in text_preview:
        article_type = "休業"  # 休業関連
    elif '対象' in text_preview or 'できる' in text_preview:
        article_type = "対象"
    elif '手続' in text_preview or '申請' in text_preview or '申出' in text_preview:
        article_type = "手続"
    elif '期間' in text_preview:
        article_type = "期間"
    
    return (article_num if article_num else None, article_type)


def calculate_intelligent_score(
    query: str,
    text: str,
    file_name: str,
    section: Optional[str],
    page_no: int
) -> Tuple[float, List[str], str]:
    """
    インテリジェントスコア計算
    
    Returns:
        (スコア, マッチした用語リスト, 関連性タイプ)
    """
    text_lower = text.lower()
    query_lower = query.lower()
    
    # 1. クエリ拡張と基本スコア
    expanded_queries = expand_query(query)
    max_score = 0
    matched_terms = []
    
    for exp_query in expanded_queries:
        # 部分一致スコア
        score = fuzz.partial_ratio(exp_query, text_lower)
        
        # 完全一致ボーナス（大幅に増やす）
        if exp_query in text_lower:
            score += 50  # 20→50に増加
            matched_terms.append(exp_query)
            
            # 出現回数に応じて追加ボーナス（ただし上限あり）
            count = text_lower.count(exp_query)
            if count > 1:
                score += min(count * 5, 30)  # 最大30点まで
        
        # キーワードマッチング
        keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', exp_query)
        for keyword in keywords:
            if len(keyword) >= 2 and keyword in text_lower:
                score += 10  # 5→10に増加
                if keyword not in matched_terms:
                    matched_terms.append(keyword)
        
        max_score = max(max_score, score)
    
    # 2. クエリ意図に基づくボーナス
    intent = analyze_query_intent(query)
    article_num, article_type = extract_article_info(text)
    
    # 意図と条文タイプのマッチング
    intent_bonus = 0
    relevance_type = "general"
    
    # キーワードが実際にテキストに含まれているかチェック
    has_relevant_content = False
    for term in matched_terms:
        if term in text_lower:
            has_relevant_content = True
            break
    
    if intent == "definition" or intent == "condition":
        # 定義や条件を求めている場合
        
        # 休暇関連の条文は特別扱い
        if article_type == "休暇":
            intent_bonus = 60  # 休暇条文は高ボーナス
            relevance_type = "definition"
        elif article_type == "休業" and "休" in query_lower:
            intent_bonus = 50
            relevance_type = "definition"
        # 第1〜3条の処理（ただし関連内容がある場合のみ）
        elif article_num and article_num <= 3:
            if has_relevant_content:
                intent_bonus = 40  # 下げる（50→40）
                relevance_type = "definition"
            else:
                intent_bonus = 5  # 大幅に下げる（20→5）
        
        # 目的・対象・定義タイプの処理
        if article_type in ["目的", "対象", "定義"]:
            if has_relevant_content:
                intent_bonus += 20  # 下げる（30→20）
            else:
                intent_bonus += 0  # 関連内容がない目的条文はボーナスなし
            relevance_type = "definition"
        elif article_type == "手続":
            intent_bonus -= 20  # 手続きは下げる
    
    elif intent == "procedure":
        # 手続きを求めている場合
        if article_type == "手続":
            intent_bonus = 40
            relevance_type = "procedure"
        elif article_type in ["目的", "対象"]:
            intent_bonus -= 10
    
    elif intent == "period":
        # 期間を求めている場合
        if "期間" in text_lower or "日" in text_lower or "ヶ月" in text_lower:
            intent_bonus = 30
            relevance_type = "period"
    
    # 3. 条文番号による重み付け（内容の関連性を重視）
    article_bonus = 0
    if article_num:
        # 関連内容がある場合のみボーナス
        if has_relevant_content:
            if article_num == 1 and article_type == "目的":
                article_bonus = 10  # 第1条でも目的のみなら控えめ
            elif article_num == 2:
                article_bonus = 15  # 第2条（定義・対象）
            elif article_num <= 5:
                article_bonus = 10
            elif article_num >= 30 and article_num <= 35:  # 休暇関連の条文番号帯
                if article_type == "休暇":
                    article_bonus = 20  # 休暇セクションの条文を優遇
            elif article_num > 50:
                article_bonus = -10  # 後半の条文は優先度下げる
        else:
            # 関連内容がない場合
            if article_num == 1:
                article_bonus = -20  # 第1条でも関連なければペナルティ
    
    # 4. ファイル名による調整
    file_bonus = 0
    if "育" in query_lower or "育休" in query_lower:
        if "育児介護" in file_name:
            file_bonus = 30
        elif "パート" in file_name:
            file_bonus = -30
    elif "パート" in query_lower:
        if "パート" in file_name:
            file_bonus = 30
        else:
            file_bonus = -20
    
    # 5. 単語出現頻度ペナルティ（多すぎる場合は手続き系の可能性）
    frequency_penalty = 0
    for term in matched_terms:
        count = text_lower.count(term.lower())
        if count > 15:  # 15回以上出現は手続き系の可能性
            if intent != "procedure":  # 手続きを求めていない場合はペナルティ
                frequency_penalty = -10
    
    # 総合スコア
    total_score = max_score + intent_bonus + article_bonus + file_bonus + frequency_penalty
    
    # デバッグログ
    logger.debug(f"""
    Page {page_no}: Score breakdown
    - Base: {max_score}
    - Intent bonus: {intent_bonus} (intent={intent}, article_type={article_type})
    - Article bonus: {article_bonus} (article_num={article_num})
    - File bonus: {file_bonus}
    - Frequency penalty: {frequency_penalty}
    - Total: {total_score}
    """)
    
    return max(0, total_score), matched_terms, relevance_type


def search_intelligent(
    query: str,
    index_path: Path = Path("./data/index.sqlite"),
    top_k: int = 5,
    min_score: int = 30
) -> List[SearchResult]:
    """
    インテリジェント検索
    
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
    
    # クエリ意図を分析
    intent = analyze_query_intent(query)
    logger.info(f"Query intent: {intent} for query: {query}")
    
    with sqlite3.connect(index_path) as db:
        cursor = db.execute(
            "SELECT file_name, file_path, page_no, text, section FROM pages"
        )
        
        for file_name, file_path, page_no, text, section in cursor:
            score, matched_terms, relevance_type = calculate_intelligent_score(
                query, text, file_name, section, page_no
            )
            
            if score >= min_score:
                results.append(SearchResult(
                    file_name=file_name,
                    file_path=file_path,
                    page_no=page_no,
                    score=score,
                    text=text,
                    section=section,
                    matched_terms=matched_terms,
                    relevance_type=relevance_type
                ))
    
    # スコアでソート
    results.sort(key=lambda x: x.score, reverse=True)
    
    # 関連性タイプが同じものを優先的にグループ化
    if results and intent in ["definition", "condition"]:
        # 定義・条件を求めている場合は、それらを上位に
        definition_results = [r for r in results if r.relevance_type == "definition"]
        other_results = [r for r in results if r.relevance_type != "definition"]
        results = definition_results + other_results
    
    return results[:top_k]


def extract_intelligent_snippet(
    text: str,
    query: str,
    matched_terms: List[str],
    relevance_type: str,
    window: int = 200
) -> str:
    """
    インテリジェント抜粋生成
    関連性タイプに応じて最適な部分を抽出
    """
    text_lower = text.lower()
    
    # 条文の開始位置を探す（定義・条件の場合）
    if relevance_type == "definition":
        # 第○条のパターンを探す
        article_pattern = re.search(r'第[０-９0-9一二三四五六七八九十]+条', text)
        if article_pattern:
            start_pos = article_pattern.start()
            # 条文の終わりまでを含める
            end_pos = min(len(text), start_pos + 400)
            excerpt = text[start_pos:end_pos]
            if end_pos < len(text):
                excerpt += "..."
            
            # マッチ用語をハイライト
            for term in matched_terms:
                pattern = re.compile(re.escape(term), re.IGNORECASE)
                excerpt = pattern.sub(f"**{term}**", excerpt)
            
            return excerpt
    
    # 通常の抜粋生成
    best_pos = -1
    best_term = query
    
    for term in matched_terms:
        pos = text_lower.find(term.lower())
        if pos != -1:
            best_pos = pos
            best_term = term
            break
    
    if best_pos == -1:
        best_pos = 0
    
    start = max(0, best_pos - window // 2)
    end = min(len(text), best_pos + len(best_term) + window // 2)
    
    excerpt = text[start:end]
    
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(text):
        excerpt = excerpt + "..."
    
    # マッチ用語をハイライト
    for term in matched_terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        excerpt = pattern.sub(f"**{term}**", excerpt)
    
    return excerpt


def generate_intelligent_answer(query: str, results: List[SearchResult]) -> Dict:
    """
    インテリジェント回答生成
    """
    if not results:
        return {
            "found": False,
            "answer": "該当する情報が見つかりませんでした。",
            "suggestions": [
                "より具体的なキーワードで検索してください",
                "育児休業に関しては「育休」「育児休業」などで検索",
                "パートタイマーに関しては「パート」「時給」などで検索"
            ]
        }
    
    best_result = results[0]
    
    # 信頼度の判定
    confidence = "high" if best_result.score >= 100 else "medium" if best_result.score >= 70 else "low"
    
    # インテリジェント抜粋
    excerpt = extract_intelligent_snippet(
        best_result.text,
        query,
        best_result.matched_terms,
        best_result.relevance_type,
        window=250
    )
    
    # クエリ意図に応じた追加情報
    intent = analyze_query_intent(query)
    additional_info = ""
    
    if intent == "definition" and best_result.relevance_type == "definition":
        additional_info = "\n\n📌 この内容は規程の基本的な定義・条件を示しています。"
    elif intent == "procedure" and best_result.relevance_type != "procedure":
        additional_info = "\n\n💡 手続きの詳細については、申請・手続きに関する条文もご確認ください。"
    
    return {
        "found": True,
        "answer": excerpt + additional_info,
        "source": {
            "file": best_result.file_name,
            "page": best_result.page_no,
            "section": best_result.section,
            "score": best_result.score,
            "confidence": confidence,
            "relevance_type": best_result.relevance_type
        },
        "all_results": [
            {
                "file": result.file_name,
                "page": result.page_no,
                "score": result.score,
                "relevance_type": result.relevance_type
            }
            for result in results
        ]
    }


# テスト
if __name__ == "__main__":
    test_queries = [
        "育休について教えて",
        "育児休業の条件は？",
        "育休の手続き方法",
        "有給休暇の繰越",
        "パートの勤務時間"
    ]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print(f"Intent: {analyze_query_intent(query)}")
        
        results = search_intelligent(query, top_k=3)
        
        for i, result in enumerate(results[:2], 1):
            print(f"\n{i}. {result.file_name} - Page {result.page_no}")
            print(f"   Score: {result.score:.1f}")
            print(f"   Type: {result.relevance_type}")
            print(f"   Matched: {', '.join(result.matched_terms)}")