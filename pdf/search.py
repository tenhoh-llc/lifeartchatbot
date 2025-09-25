"""
検索・ランキングモジュール
rapidfuzzを使用した類似度検索とスコアリング
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import re
from rapidfuzz import fuzz
from loguru import logger
from .index import get_all_pages


@dataclass
class SearchHit:
    """
    検索結果を保持するデータクラス
    """
    file_name: str          # PDFファイル名
    page_no: int            # ページ番号
    score: float            # 検索スコア（0-100）
    text: str               # ページのテキスト
    section: Optional[str]  # セクション名
    file_path: str          # ファイルパス


# 同義語辞書
SYNONYMS = {
    "有給": ["有休", "年休", "年次有給", "年次有給休暇"],
    "給与": ["給料", "賃金", "報酬"],
    "時短": ["時間短縮", "短時間勤務"],
    "遅刻": ["遅参", "遅れ"],
    "早退": ["早引け", "早帰り"],
    "欠勤": ["欠席", "休み"],
}


def normalize_text(text: str, expand_synonyms: bool = True) -> str:
    """
    テキストの正規化
    検索精度を向上させるための前処理
    
    Args:
        text: 正規化前のテキスト
    
    Returns:
        正規化後のテキスト
    
    処理内容:
    - 大文字小文字の統一
    - 全角半角の統一
    - 句読点の除去
    """
    if not text:
        return ""
    
    # 全角英数字を半角に変換
    text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    text = text.translate(str.maketrans(
        'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    ))
    # 小文字化
    text = text.lower()
    # 記号除去（句読点、括弧など）
    text = re.sub(r'[、。！？「」『』（）\(\)\[\]【】]', ' ', text)
    # 連続空白を単一スペースに圧縮
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 同義語展開
    if expand_synonyms:
        for base, synonyms in SYNONYMS.items():
            if base in text:
                for syn in synonyms:
                    text = text + " " + syn
    
    return text


def calculate_score(
    query: str,
    text: str,
    section: Optional[str] = None,
    boost_keywords: Optional[List[str]] = None
) -> float:
    """
    検索スコアを計算
    
    Args:
        query: 検索クエリ
        text: 検索対象テキスト
        section: セクション名
        boost_keywords: ブースト対象のキーワードリスト
    
    Returns:
        スコア（0-100+）
    
    スコアリングアルゴリズム:
    1. 基本スコア: rapidfuzzによる部分一致度
    2. セクションボーナス: セクションに含まれる場合+10
    3. キーワードボーナス: 重要キーワードが含まれる場合+5
    4. 完全一致ボーナス: 完全一致する場合+20
    5. 類義語ボーナス: 類義語が含まれる場合のボーナス
    """
    # 正規化
    query_norm = normalize_text(query)
    text_norm = normalize_text(text)
    
    # 基本スコア（部分一致度）
    # partial_ratio: 部分文字列の一致度を計算
    base_score = fuzz.partial_ratio(query_norm, text_norm)
    
    # セクションボーナス
    section_bonus = 0
    if section:
        section_norm = normalize_text(section)
        if query_norm in section_norm:
            section_bonus = 15
        elif fuzz.partial_ratio(query_norm, section_norm) > 80:
            section_bonus = 10
    
    # キーワードボーナス（類義語を含む）
    keyword_bonus = 0
    if boost_keywords:
        for keyword in boost_keywords:
            keyword_norm = normalize_text(keyword)
            if keyword_norm in text_norm:
                # 元のクエリから抽出された単語の場合は高いボーナス
                if keyword_norm in query_norm:
                    keyword_bonus += 10
                else:
                    # 類義語の場合は少し低いボーナス
                    keyword_bonus += 7
    
    # 完全一致ボーナス
    exact_match_bonus = 0
    if query_norm in text_norm:
        exact_match_bonus = 20
    
    # 位置ボーナス（クエリが早い位置に出現する場合）
    position_bonus = 0
    pos = text_norm.find(query_norm)
    if pos >= 0:
        # テキストの前半25%に出現する場合ボーナス
        if pos < len(text_norm) * 0.25:
            position_bonus = 10
        elif pos < len(text_norm) * 0.5:
            position_bonus = 5
    
    # 類義語に対する位置ボーナス
    if boost_keywords and position_bonus == 0:
        for keyword in boost_keywords:
            keyword_norm = normalize_text(keyword)
            pos = text_norm.find(keyword_norm)
            if pos >= 0:
                if pos < len(text_norm) * 0.25:
                    position_bonus = max(position_bonus, 8)  # 類義語は少し低め
                elif pos < len(text_norm) * 0.5:
                    position_bonus = max(position_bonus, 4)
    
    # 総合スコア
    total_score = base_score + section_bonus + keyword_bonus + exact_match_bonus + position_bonus
    
    return min(total_score, 150)  # 最大150点


def get_synonyms(word: str) -> List[str]:
    """
    単語の類義語を取得
    
    Args:
        word: 検索語
        
    Returns:
        類義語のリスト（元の語を含む）
    """
    # 類義語辞書（簡易版）
    synonym_map = {
        '時間外労働': ['時間外勤務', '残業', 'オーバータイム'],
        '時間外勤務': ['時間外労働', '残業', 'オーバータイム'],
        '残業': ['時間外労働', '時間外勤務', 'オーバータイム'],
        '給与': ['給料', '賃金', '報酬', 'サラリー'],
        '給料': ['給与', '賃金', '報酬', 'サラリー'],
        '休暇': ['休み', '休日', 'ホリデー'],
        '育児': ['子育て', 'チャイルドケア'],
        '勤務': ['労働', '仕事', 'ワーク'],
        '労働': ['勤務', '仕事', 'ワーク'],
    }
    
    # 元の単語を含めた類義語リストを返す
    synonyms = [word]
    if word in synonym_map:
        synonyms.extend(synonym_map[word])
    
    return list(set(synonyms))  # 重複を除去


def extract_keywords(query: str) -> List[str]:
    """
    クエリから重要キーワードを抽出
    
    Args:
        query: 検索クエリ
    
    Returns:
        キーワードのリスト（類義語を含む）
    """
    # 簡易的なキーワード抽出
    # 本番環境では形態素解析を使用することを推奨
    
    # ストップワード（除外する単語）
    stopwords = {
        'の', 'は', 'が', 'を', 'に', 'で', 'と', 'から', 'まで',
        'について', 'に関して', 'とは', 'って', 'です', 'ます', '教えて',
        '？', '?', '条件', 'ください', '教えてください', '知りたい',
        '教える', 'おしえて', '教えて下さい'
    }
    
    # クエリをクリーンアップ
    query_clean = query.replace('？', '').replace('?', '').replace('！', '').replace('!', '')
    
    # まず助詞などで分割してみる
    base_words = []
    
    # 「について」「の」などで分割
    parts = re.split(r'について|に関して|とは|は？|は', query_clean)
    
    for part in parts:
        part = part.strip()
        if part and part not in stopwords:
            # さらに細かく分割
            sub_words = re.split(r'[\s、。,.\-　の]+', part)
            for word in sub_words:
                word = word.strip()
                if word and word not in stopwords and len(word) > 1:
                    base_words.append(word)
    
    # 主要な複合語も抽出
    compound_patterns = [
        r'時間外労働',
        r'時間外勤務',
        r'有給休暇',
        r'育児休業',
        r'育休',
        r'産休',
        r'時短勤務',
        r'給与支払',
        r'パート'
    ]
    
    for pattern in compound_patterns:
        if re.search(pattern, query):
            match = re.search(pattern, query)
            if match:
                base_words.append(match.group(0))
    
    # ストップワードを除外（複合語は除く）
    base_keywords = []
    for w in base_words:
        if w and w not in stopwords and len(w) > 1:
            # 「教えてください」のような長い語は無視
            if not any(stop in w for stop in ['教えて', 'ください', '知りたい']):
                base_keywords.append(w)
    
    # 類義語を追加
    all_keywords = []
    for keyword in base_keywords:
        synonyms = get_synonyms(keyword)
        all_keywords.extend(synonyms)
    
    return list(set(all_keywords))  # 重複を除去


def search(
    query: str,
    top_k: int = 5,
    index_path: Path | str = "./data/index.sqlite",
    min_score: float = 30.0,
    context: str = None
) -> List[SearchHit]:
    """
    テキスト検索を実行
    
    Args:
        query: 検索クエリ
        top_k: 返す結果の最大数
        index_path: インデックスデータベースのパス
        min_score: 最小スコア閾値
    
    Returns:
        検索結果のリスト（スコア順）
    
    検索プロセス:
    1. データベースから全ページを取得
    2. 各ページに対してスコアを計算
    3. スコアでソートして上位k件を返す
    """
    if not query:
        logger.warning("Empty query provided")
        return []
    
    # Pathオブジェクトに変換
    if isinstance(index_path, str):
        index_path = Path(index_path)
    
    # データベースが存在しない場合
    if not index_path.exists():
        logger.error(f"Index database not found: {index_path}")
        return []
    
    logger.info(f"Searching for: {query[:50]}...")
    
    # 文脈を考慮したクエリの拡張
    expanded_query = query
    if context:
        # 「取れない」「できない」などの否定的な質問の場合、検索キーワードを調整
        if any(word in query for word in ["取れない", "できない", "対象外", "除外"]):
            # 文脈から主題を抽出（例：育児休業）
            if "育" in context:
                expanded_query = "育児休業 対象外 除外 条件 要件 資格"
            elif "有給" in context or "有休" in context:
                expanded_query = "有給休暇 付与 対象外 条件"
            elif "時間外" in context or "残業" in context:
                expanded_query = "時間外労働 制限 上限 対象外"
    
    # キーワード抽出
    keywords = extract_keywords(expanded_query)
    logger.debug(f"Extracted keywords: {keywords}")
    
    # 全ページを取得
    try:
        pages = get_all_pages(index_path)
    except Exception as e:
        logger.error(f"Failed to fetch pages: {e}")
        return []
    
    if not pages:
        logger.warning("No pages in index")
        return []
    
    # 各ページに対してスコアを計算
    hits: List[SearchHit] = []
    
    for file_name, page_no, text, section, file_path in pages:
        # スコア計算
        score = calculate_score(
            query=query,
            text=text,
            section=section,
            boost_keywords=keywords
        )
        
        # 閾値以上のスコアのみ保持
        if score >= min_score:
            hit = SearchHit(
                file_name=file_name,
                page_no=page_no,
                score=score,
                text=text,
                section=section,
                file_path=file_path
            )
            hits.append(hit)
    
    # スコアでソート（降順）
    hits.sort(key=lambda x: x.score, reverse=True)
    
    # デバッグ情報
    if hits:
        logger.info(f"Found {len(hits)} results, top score: {hits[0].score:.1f}")
    else:
        logger.info("No results found")
    
    # 上位k件を返す
    return hits[:top_k]


def search_with_context(
    query: str,
    context_queries: List[str] = None,
    top_k: int = 5,
    index_path: Path | str = "./data/index.sqlite"
) -> List[SearchHit]:
    """
    コンテキストを考慮した検索
    関連するクエリも同時に検索してスコアを調整
    
    Args:
        query: メインの検索クエリ
        context_queries: 関連クエリのリスト
        top_k: 返す結果の最大数
        index_path: インデックスデータベースのパス
    
    Returns:
        検索結果のリスト
    """
    # メイン検索
    main_hits = search(query, top_k * 2, index_path)
    
    if not context_queries or not main_hits:
        return main_hits[:top_k]
    
    # コンテキストクエリでも検索
    context_scores = {}
    for context_query in context_queries:
        context_hits = search(context_query, top_k, index_path)
        for hit in context_hits:
            key = (hit.file_name, hit.page_no)
            if key not in context_scores:
                context_scores[key] = 0
            context_scores[key] += hit.score * 0.3  # コンテキストの重み
    
    # メインヒットのスコアを調整
    for hit in main_hits:
        key = (hit.file_name, hit.page_no)
        if key in context_scores:
            hit.score += context_scores[key]
    
    # 再ソート
    main_hits.sort(key=lambda x: x.score, reverse=True)
    
    return main_hits[:top_k]