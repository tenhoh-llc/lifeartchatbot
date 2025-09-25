"""
検索機能のテスト
"""
import pytest
from pdf.search import (
    normalize_text,
    calculate_score,
    extract_keywords,
    SearchHit
)


class TestTextNormalization:
    """テキスト正規化のテスト"""
    
    def test_normalize_converts_to_lowercase(self):
        """小文字変換のテスト"""
        text = "Hello WORLD"
        result = normalize_text(text)
        assert result == "hello world"
    
    def test_normalize_converts_fullwidth_to_halfwidth(self):
        """全角から半角への変換テスト"""
        text = "ＡＢＣ１２３"
        result = normalize_text(text)
        assert "ABC123" in result
    
    def test_normalize_removes_punctuation(self):
        """句読点の削除テスト"""
        text = "これは、テストです。"
        result = normalize_text(text)
        assert "、" not in result
        assert "。" not in result
    
    def test_normalize_handles_empty_string(self):
        """空文字列の処理テスト"""
        result = normalize_text("")
        assert result == ""


class TestScoreCalculation:
    """スコア計算のテスト"""
    
    def test_calculate_score_basic(self):
        """基本的なスコア計算テスト"""
        score = calculate_score(
            query="有給休暇",
            text="有給休暇について説明します"
        )
        assert score > 0
    
    def test_calculate_score_with_section_bonus(self):
        """セクションボーナスのテスト"""
        score_without_section = calculate_score(
            query="有給",
            text="本文には有給の記載があります"
        )
        score_with_section = calculate_score(
            query="有給",
            text="本文には有給の記載があります",
            section="有給休暇について"
        )
        assert score_with_section > score_without_section
    
    def test_calculate_score_exact_match_bonus(self):
        """完全一致ボーナスのテスト"""
        score = calculate_score(
            query="完全一致",
            text="これは完全一致するテキストです"
        )
        assert score > 50  # 基本スコア + ボーナス
    
    def test_calculate_score_no_match(self):
        """マッチしない場合のテスト"""
        score = calculate_score(
            query="存在しない",
            text="全く関係ないテキスト"
        )
        assert score < 30


class TestKeywordExtraction:
    """キーワード抽出のテスト"""
    
    def test_extract_keywords_removes_stopwords(self):
        """ストップワード除去のテスト"""
        keywords = extract_keywords("これは有給休暇について")
        assert "これ" not in keywords
        assert "について" not in keywords
        assert "有給休暇" in keywords or "有給" in keywords
    
    def test_extract_keywords_splits_by_space(self):
        """スペース区切りのテスト"""
        keywords = extract_keywords("有給 休暇 申請")
        assert len(keywords) >= 2
    
    def test_extract_keywords_handles_empty_query(self):
        """空クエリの処理テスト"""
        keywords = extract_keywords("")
        assert keywords == []


class TestSearchHit:
    """SearchHitデータクラスのテスト"""
    
    def test_search_hit_creation(self):
        """SearchHitの作成テスト"""
        hit = SearchHit(
            file_name="test.pdf",
            page_no=1,
            score=85.5,
            text="テスト文書",
            section="第1条",
            file_path="/path/to/test.pdf"
        )
        assert hit.file_name == "test.pdf"
        assert hit.page_no == 1
        assert hit.score == 85.5
        assert hit.section == "第1条"
    
    def test_search_hit_sorting(self):
        """SearchHitのソートテスト"""
        hits = [
            SearchHit("a.pdf", 1, 50.0, "text1", None, "/a.pdf"),
            SearchHit("b.pdf", 1, 80.0, "text2", None, "/b.pdf"),
            SearchHit("c.pdf", 1, 65.0, "text3", None, "/c.pdf"),
        ]
        sorted_hits = sorted(hits, key=lambda x: x.score, reverse=True)
        assert sorted_hits[0].score == 80.0
        assert sorted_hits[1].score == 65.0
        assert sorted_hits[2].score == 50.0