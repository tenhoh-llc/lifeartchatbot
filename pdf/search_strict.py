"""
厳格な検索モジュール
許可ファイル制限とスコアしきい値を実装
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
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


# 同義語辞書
SYNONYMS = {
    "有給": ["有休", "年休", "年次有給", "年次有給休暇"],
    "給与": ["給料", "賃金", "報酬"],
    "時短": ["時間短縮", "短時間勤務"],
    "遅刻": ["遅参", "遅れ"],
    "早退": ["早引け", "早帰り"],
    "欠勤": ["欠席", "休み"],
}


def _normalize(text: str, expand_synonyms: bool = True) -> str:
    """テキストを正規化"""
    # 全角英数字を半角に変換
    text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    text = text.translate(str.maketrans(
        'ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    ))
    # 小文字化
    text = text.lower()
    # 記号除去
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


def search_strict(
    query: str,
    top_k: int = 5,
    index_path: Path = Path("./data/index.sqlite"),
    allowed_files: Tuple[str, ...] = ("就業規則", "給与"),
    strict: bool = True
) -> List[SearchHit]:
    """
    厳格な検索を実行
    
    Args:
        query: 検索クエリ
        top_k: 返す結果の最大数
        index_path: インデックスDBのパス
        allowed_files: 許可するファイル名の部分文字列
        strict: 厳格モード（しきい値適用）
        
    Returns:
        検索結果のリスト
    """
    if not query:
        return []
    
    if not index_path.exists():
        logger.error(f"Index not found: {index_path}")
        return []
    
    query_normalized = _normalize(query)
    hits = []
    
    with sqlite3.connect(index_path) as db:
        cursor = db.execute(
            "SELECT file_name, file_path, page_no, text, section FROM pages"
        )
        for file_name, file_path, page_no, text, section in cursor:
            # ファイル名フィルタリング（重要）
            if allowed_files and not any(af in file_name for af in allowed_files):
                logger.debug(f"Skipping {file_name} (not in allowed files)")
                continue
            
            # スコア計算
            score = fuzz.partial_ratio(query_normalized, _normalize(text))
            
            # セクションボーナス
            if section:
                section_normalized = _normalize(section, expand_synonyms=False)
                if query_normalized in section_normalized or \
                   re.search(r'第[\d一二三四五六七八九十]+条', section):
                    score += 5
            
            if score > 0:
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
    
    # 厳格モードでのしきい値適用
    if strict and hits:
        top_score = hits[0].score
        if top_score >= 80:
            # スコア80以上: 1件のみ
            return hits[:1]
        elif 70 <= top_score < 80:
            # スコア70-79: 最大2件
            filtered = [h for h in hits[:2] if h.score >= 70]
            return filtered
        else:
            # スコア70未満: 無回答
            logger.info(f"Top score {top_score} below threshold 70")
            return []
    
    return hits[:top_k]