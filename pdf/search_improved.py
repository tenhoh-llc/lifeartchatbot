"""
改善された検索モジュール
質問の文脈に応じて適切なPDFから回答を取得
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import sqlite3
from pathlib import Path
from rapidfuzz import fuzz
import re
from loguru import logger


@dataclass
class SearchHit:
    file_name: str
    file_path: str
    page_no: int
    score: float
    text: str
    section: Optional[str]


# ファイルごとの専門分野定義
FILE_TOPICS = {
    "育児介護": ["育児", "介護", "産前", "産後", "出産", "子育て", "看護", "家族"],
    "パート": ["パート", "アルバイト", "非正規", "時給", "短時間"],
    "労使協定": ["協定", "労使", "36協定", "労働者代表"],
}

# 一般的な就業規則のトピック
GENERAL_TOPICS = ["有給", "有休", "年休", "給与", "給料", "賃金", "勤務時間", "残業", "遅刻", "早退", "欠勤", "退職", "解雇", "懲戒"]


def identify_query_topic(query: str) -> str:
    """質問のトピックを特定"""
    query_lower = query.lower()
    
    # 「育休」は「育児介護」として認識
    if "育休" in query_lower or "育児休" in query_lower:
        return "育児介護"
    
    # 特定ファイルのトピックをチェック
    for file_type, keywords in FILE_TOPICS.items():
        if any(kw in query_lower for kw in keywords):
            return file_type
    
    # 一般的な就業規則のトピック
    if any(kw in query_lower for kw in GENERAL_TOPICS):
        return "general"
    
    return "unknown"


def calculate_relevance_score(query: str, text: str, file_name: str, section: Optional[str]) -> float:
    """
    文脈を考慮した関連性スコアを計算
    """
    query_lower = query.lower()
    text_lower = text.lower()
    
    # 基本スコア（部分一致）
    base_score = fuzz.partial_ratio(query_lower, text_lower)
    
    # デバッグ用ログ
    logger.debug(f"File: {file_name}, Base score: {base_score}")
    
    # トピック一致ボーナス
    topic_bonus = 0
    query_topic = identify_query_topic(query)
    
    if query_topic == "育児介護":
        if "育児介護" in file_name:
            topic_bonus = 50  # 育児介護の質問は育児介護規程を強く優先
        else:
            topic_bonus = -30  # 他のファイルはペナルティ
    elif query_topic == "パート":
        if "パート" in file_name:
            topic_bonus = 50  # パートの質問はパート規程を強く優先
        else:
            topic_bonus = -30  # 他のファイルはペナルティ
    elif query_topic == "general":
        if "育児介護" not in file_name and "パート" not in file_name:
            topic_bonus = 20  # 一般的な質問は特殊規程を避ける
        else:
            topic_bonus = -10
    
    # セクションボーナス
    section_bonus = 0
    if section:
        if re.search(r'第[\d一二三四五六七八九十]+条', section):
            section_bonus = 10
        if query_lower in section.lower():
            section_bonus += 15
    
    # キーワード密度ボーナス
    keyword_bonus = 0
    keywords = extract_keywords(query)
    for keyword in keywords:
        count = text_lower.count(keyword.lower())
        if count > 0:
            keyword_bonus += min(count * 2, 10)
    
    # クエリの単語が直接含まれるかチェック
    direct_match_bonus = 0
    query_words = query.split()
    for word in query_words:
        if len(word) >= 2 and word.lower() in text_lower:
            direct_match_bonus += 15
    
    total_score = base_score + topic_bonus + section_bonus + keyword_bonus + direct_match_bonus
    
    logger.debug(f"Total score for {file_name}: {total_score} (base={base_score}, topic={topic_bonus}, section={section_bonus}, keyword={keyword_bonus}, direct={direct_match_bonus})")
    
    return max(0, total_score)


def extract_keywords(query: str) -> List[str]:
    """重要キーワードを抽出"""
    # 不要な語を除去
    stopwords = ["について", "教えて", "ください", "とは", "何", "どう", "いつ", "どこ"]
    
    keywords = []
    for word in re.split(r'[、。\s？！]', query):
        word = word.strip()
        if word and word not in stopwords and len(word) > 1:
            keywords.append(word)
    
    return keywords


def search_improved(
    query: str,
    index_path: Path = Path("./data/index.sqlite"),
    top_k: int = 5
) -> List[SearchHit]:
    """
    改善された検索を実行
    
    Args:
        query: 検索クエリ
        index_path: インデックスDBのパス
        top_k: 返す結果の最大数
        
    Returns:
        検索結果のリスト
    """
    if not query:
        return []
    
    if not index_path.exists():
        logger.error(f"Index not found: {index_path}")
        return []
    
    hits = []
    
    with sqlite3.connect(index_path) as db:
        cursor = db.execute(
            "SELECT file_name, file_path, page_no, text, section FROM pages"
        )
        for file_name, file_path, page_no, text, section in cursor:
            # 関連性スコアを計算
            score = calculate_relevance_score(query, text, file_name, section)
            
            if score > 30:  # 最低スコアのしきい値
                hits.append(SearchHit(
                    file_name=file_name,
                    file_path=file_path,
                    page_no=page_no,
                    score=score,
                    text=text,
                    section=section
                ))
    
    # スコアでソート
    hits.sort(key=lambda x: x.score, reverse=True)
    
    # 上位結果のみ返す
    return hits[:top_k]


def generate_answer_from_hits(query: str, hits: List[SearchHit]) -> Dict[str, any]:
    """
    検索結果から適切な回答を生成
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
    confidence = "high" if best_hit.score >= 80 else "medium" if best_hit.score >= 60 else "low"
    
    # テキストから重要部分を抽出
    keywords = extract_keywords(query)
    relevant_sentences = []
    
    sentences = re.split(r'[。\n]', best_hit.text)
    
    # キーワードを含む文を優先的に抽出
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # キーワードが含まれるかチェック
        keyword_count = sum(1 for kw in keywords if kw.lower() in sentence.lower())
        if keyword_count > 0:
            relevant_sentences.append((keyword_count, sentence))
    
    # キーワード数でソート
    relevant_sentences.sort(key=lambda x: x[0], reverse=True)
    
    # 最も関連性の高い部分を選択
    if relevant_sentences:
        # 最大300文字程度に制限
        excerpt_parts = []
        total_length = 0
        for _, sentence in relevant_sentences:
            if total_length + len(sentence) <= 300:
                excerpt_parts.append(sentence)
                total_length += len(sentence)
            else:
                break
        excerpt = "。".join(excerpt_parts)
        if not excerpt.endswith("。"):
            excerpt += "。"
    else:
        # キーワードが見つからない場合は条文番号を含む部分を探す
        article_sentences = []
        for sentence in sentences:
            if re.search(r'第[一二三四五六七八九十０-９ー−]+条', sentence):
                article_sentences.append(sentence.strip())
        
        if article_sentences:
            excerpt = "。".join(article_sentences[:2]) + "。"
        else:
            # それでも見つからない場合は先頭部分
            clean_sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
            excerpt = "。".join(clean_sentences[:3])
            if excerpt and not excerpt.endswith("。"):
                excerpt += "。"
    
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