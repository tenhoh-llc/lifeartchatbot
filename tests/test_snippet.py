"""
スニペット生成機能のテスト
"""
import pytest
from pdf.snippet import (
    find_all_positions,
    extract_window,
    highlight_text,
    make_snippet,
    merge_ranges,
    Snippet
)


class TestFindPositions:
    """位置検索機能のテスト"""
    
    def test_find_single_position(self):
        """単一の位置検索テスト"""
        positions = find_all_positions("hello world", "world")
        assert len(positions) == 1
        assert positions[0] == (6, 11)
    
    def test_find_multiple_positions(self):
        """複数の位置検索テスト"""
        positions = find_all_positions("test test test", "test")
        assert len(positions) == 3
    
    def test_find_case_insensitive(self):
        """大文字小文字を無視した検索テスト"""
        positions = find_all_positions("Hello HELLO", "hello", case_sensitive=False)
        assert len(positions) == 2
    
    def test_find_no_match(self):
        """マッチしない場合のテスト"""
        positions = find_all_positions("hello world", "xyz")
        assert len(positions) == 0


class TestExtractWindow:
    """ウィンドウ抽出のテスト"""
    
    def test_extract_window_center(self):
        """中央からのウィンドウ抽出テスト"""
        text = "0123456789" * 10
        start, end = extract_window(text, 50, 10, 100)
        assert start <= 50
        assert end >= 50
        assert end - start <= 20 + 10  # ウィンドウサイズ + 余裕
    
    def test_extract_window_at_start(self):
        """開始位置でのウィンドウ抽出テスト"""
        text = "0123456789" * 10
        start, end = extract_window(text, 5, 10, 100)
        assert start == 0
        assert end > 5
    
    def test_extract_window_at_end(self):
        """終了位置でのウィンドウ抽出テスト"""
        text = "0123456789" * 10
        start, end = extract_window(text, 95, 10, 100)
        assert start < 95
        assert end == 100


class TestHighlightText:
    """テキストハイライトのテスト"""
    
    def test_highlight_markdown(self):
        """Markdownハイライトのテスト"""
        result = highlight_text("これは有給のテスト", "有給")
        assert "**有給**" in result
    
    def test_highlight_case_insensitive(self):
        """大文字小文字を無視したハイライトテスト"""
        result = highlight_text("Hello WORLD", "world")
        assert "**WORLD**" in result or "**world**" in result.lower()
    
    def test_highlight_no_match(self):
        """マッチしない場合のハイライトテスト"""
        text = "これはテストです"
        result = highlight_text(text, "存在しない")
        assert result == text


class TestMakeSnippet:
    """スニペット生成のテスト"""
    
    def test_make_snippet_basic(self):
        """基本的なスニペット生成テスト"""
        text = "これは長いテキストです。検索キーワードが含まれています。後続の文章。"
        snippet = make_snippet(text, "キーワード", window=10)
        assert "キーワード" in snippet.excerpt
        assert "**キーワード**" in snippet.excerpt
    
    def test_make_snippet_with_ellipsis(self):
        """省略記号付きスニペット生成テスト"""
        text = "a" * 1000
        snippet = make_snippet(text + "キーワード" + text, "キーワード", window=10)
        assert "…" in snippet.excerpt
    
    def test_make_snippet_no_query(self):
        """クエリなしのスニペット生成テスト"""
        text = "これはテストテキストです"
        snippet = make_snippet(text, "", max_length=10)
        assert len(snippet.excerpt) <= 11  # 省略記号含む
    
    def test_make_snippet_no_match(self):
        """マッチしない場合のスニペット生成テスト"""
        text = "これはテストテキストです"
        snippet = make_snippet(text, "存在しない", max_length=20)
        assert snippet.excerpt.startswith(text[:20]) or snippet.excerpt.startswith(text)


class TestMergeRanges:
    """範囲マージのテスト"""
    
    def test_merge_overlapping_ranges(self):
        """重複する範囲のマージテスト"""
        ranges = [(0, 10), (5, 15), (20, 30)]
        merged = merge_ranges(ranges)
        assert len(merged) == 2
        assert merged[0] == (0, 15)
        assert merged[1] == (20, 30)
    
    def test_merge_adjacent_ranges(self):
        """隣接する範囲のマージテスト"""
        ranges = [(0, 10), (10, 20), (20, 30)]
        merged = merge_ranges(ranges)
        assert len(merged) == 1
        assert merged[0] == (0, 30)
    
    def test_merge_empty_ranges(self):
        """空の範囲リストのマージテスト"""
        merged = merge_ranges([])
        assert merged == []
    
    def test_merge_single_range(self):
        """単一範囲のマージテスト"""
        ranges = [(10, 20)]
        merged = merge_ranges(ranges)
        assert merged == [(10, 20)]