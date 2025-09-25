"""
スニペット生成モジュール
検索結果から関連部分を抜粋してハイライト表示
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
import re
from loguru import logger


@dataclass
class Snippet:
    """
    テキストスニペット（抜粋）を保持するクラス
    """
    excerpt: str    # 抜粋されたテキスト（Markdown形式）
    start: int      # 元テキストでの開始位置
    end: int        # 元テキストでの終了位置


def find_all_positions(text: str, query: str, case_sensitive: bool = False) -> List[Tuple[int, int]]:
    """
    テキスト内でクエリが出現する全ての位置を検索
    
    Args:
        text: 検索対象のテキスト
        query: 検索クエリ
        case_sensitive: 大文字小文字を区別するか
    
    Returns:
        (開始位置, 終了位置)のタプルのリスト
    """
    positions = []
    
    if not text or not query:
        return positions
    
    # 大文字小文字の処理
    search_text = text if case_sensitive else text.lower()
    search_query = query if case_sensitive else query.lower()
    
    # 全ての出現位置を検索
    start = 0
    while True:
        pos = search_text.find(search_query, start)
        if pos == -1:
            break
        positions.append((pos, pos + len(query)))
        start = pos + 1
    
    return positions


def extract_window(
    text: str,
    center: int,
    window_size: int,
    text_length: int
) -> Tuple[int, int]:
    """
    中心位置から前後のウィンドウを計算
    
    Args:
        text: 元のテキスト
        center: 中心位置
        window_size: ウィンドウサイズ（前後それぞれ）
        text_length: テキスト全体の長さ
    
    Returns:
        (開始位置, 終了位置)のタプル
    """
    # 開始位置
    start = max(0, center - window_size)
    
    # 文の境界に合わせる（できるだけ文の途中で切らない）
    if start > 0:
        # 句点を探す
        for separator in ['。', '．', '\n', '！', '？']:
            sep_pos = text.rfind(separator, start, center)
            if sep_pos != -1 and sep_pos > start - 50:
                start = sep_pos + 1
                break
    
    # 終了位置
    end = min(text_length, center + window_size)
    
    # 文の境界に合わせる
    if end < text_length:
        for separator in ['。', '．', '\n', '！', '？']:
            sep_pos = text.find(separator, center, end)
            if sep_pos != -1 and sep_pos < end + 50:
                end = sep_pos + 1
                break
    
    return start, end


def highlight_text(text: str, query: str, markdown: bool = True) -> str:
    """
    テキスト内のクエリをハイライト
    
    Args:
        text: 対象テキスト
        query: ハイライトするクエリ
        markdown: Markdown形式でハイライトするか
    
    Returns:
        ハイライト済みテキスト
    """
    if not query or not text:
        return text
    
    # Markdownの場合は太字でハイライト
    if markdown:
        # 大文字小文字を無視した置換
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        highlighted = pattern.sub(lambda m: f"**{m.group()}**", text)
    else:
        # HTMLの場合
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        highlighted = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", text)
    
    return highlighted


def make_snippet(
    text: str,
    query: str,
    window: int = 120,
    max_length: int = 400,
    show_all_matches: bool = False
) -> Snippet:
    """
    テキストから検索クエリ周辺の抜粋を生成
    
    Args:
        text: 元のテキスト
        query: 検索クエリ
        window: 各マッチの前後に含める文字数
        max_length: スニペットの最大長
        show_all_matches: 全てのマッチを表示するか
    
    Returns:
        スニペットオブジェクト
    
    処理フロー:
    1. クエリの出現位置を全て検索
    2. 各位置の周辺テキストを抽出
    3. 重複を除いて結合
    4. ハイライトを適用
    """
    if not text:
        return Snippet("", 0, 0)
    
    if not query:
        # クエリがない場合は先頭から抽出
        excerpt = text[:max_length]
        if len(text) > max_length:
            excerpt += "…"
        return Snippet(excerpt, 0, min(max_length, len(text)))
    
    # クエリの全出現位置を検索
    positions = find_all_positions(text, query)
    
    if not positions:
        # マッチしない場合は先頭から抽出
        excerpt = text[:max_length]
        if len(text) > max_length:
            excerpt += "…"
        return Snippet(excerpt, 0, min(max_length, len(text)))
    
    # スニペットの範囲を計算
    snippets_ranges = []
    
    if show_all_matches:
        # 全てのマッチを含める
        for pos_start, pos_end in positions:
            center = (pos_start + pos_end) // 2
            range_start, range_end = extract_window(text, center, window, len(text))
            snippets_ranges.append((range_start, range_end))
    else:
        # 最初のマッチのみ、または最も重要なマッチ
        pos_start, pos_end = positions[0]
        center = (pos_start + pos_end) // 2
        range_start, range_end = extract_window(text, center, window, len(text))
        snippets_ranges.append((range_start, range_end))
        
        # 2つ目のマッチも含める（離れている場合）
        if len(positions) > 1:
            pos2_start, pos2_end = positions[1]
            if pos2_start > range_end + 50:  # 十分離れている場合
                center2 = (pos2_start + pos2_end) // 2
                range2_start, range2_end = extract_window(text, center2, window // 2, len(text))
                snippets_ranges.append((range2_start, range2_end))
    
    # 範囲をマージ（重複を除く）
    merged_ranges = merge_ranges(snippets_ranges)
    
    # スニペットを構築
    excerpt_parts = []
    total_length = 0
    
    for i, (start, end) in enumerate(merged_ranges):
        if total_length >= max_length:
            break
        
        # 残り文字数を計算
        remaining = max_length - total_length
        part_text = text[start:min(end, start + remaining)]
        
        # 前後の省略記号
        if start > 0 and i == 0:
            part_text = "…" + part_text
        if end < len(text) and (i == len(merged_ranges) - 1 or total_length + len(part_text) >= max_length):
            part_text = part_text + "…"
        
        # 範囲間の省略記号
        if i > 0:
            excerpt_parts.append(" … ")
            total_length += 3
        
        excerpt_parts.append(part_text)
        total_length += len(part_text)
    
    # 結合してハイライト
    excerpt = "".join(excerpt_parts)
    excerpt = highlight_text(excerpt, query)
    
    # 最初と最後の位置を記録
    final_start = merged_ranges[0][0] if merged_ranges else 0
    final_end = merged_ranges[-1][1] if merged_ranges else len(text)
    
    return Snippet(excerpt, final_start, final_end)


def merge_ranges(ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    重複する範囲をマージ
    
    Args:
        ranges: (開始, 終了)のタプルのリスト
    
    Returns:
        マージされた範囲のリスト
    """
    if not ranges:
        return []
    
    # ソート
    sorted_ranges = sorted(ranges, key=lambda x: x[0])
    
    merged = [sorted_ranges[0]]
    
    for current_start, current_end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        
        # 重複または隣接している場合はマージ
        if current_start <= last_end + 10:  # 10文字の余裕を持たせる
            merged[-1] = (last_start, max(last_end, current_end))
        else:
            merged.append((current_start, current_end))
    
    return merged


def create_summary_snippet(
    text: str,
    queries: List[str],
    max_length: int = 500
) -> str:
    """
    複数のクエリに基づいてサマリースニペットを生成
    
    Args:
        text: 元のテキスト
        queries: 検索クエリのリスト
        max_length: スニペットの最大長
    
    Returns:
        サマリーテキスト
    """
    if not text:
        return ""
    
    # 各クエリのスニペットを生成
    snippets = []
    for query in queries:
        if query:
            snippet = make_snippet(text, query, window=60, max_length=max_length // len(queries))
            if snippet.excerpt:
                snippets.append(snippet.excerpt)
    
    if not snippets:
        # クエリがマッチしない場合は先頭を返す
        summary = text[:max_length]
        if len(text) > max_length:
            summary += "…"
        return summary
    
    # スニペットを結合
    return " … ".join(snippets)[:max_length]