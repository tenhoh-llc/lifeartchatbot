"""
PDF抽出機能のテスト
"""
import pytest
from pathlib import Path
import tempfile
from pdf.ingest import clean_text, extract_section, PageRecord


class TestTextCleaning:
    """テキストクリーニング機能のテスト"""
    
    def test_clean_text_removes_extra_spaces(self):
        """連続する空白の削除テスト"""
        text = "これは    テスト　　　です"
        result = clean_text(text)
        assert result == "これは テスト です"
    
    def test_clean_text_removes_page_numbers(self):
        """ページ番号の削除テスト"""
        text = "本文\n- 1 -\n続き"
        result = clean_text(text)
        assert "- 1 -" not in result
    
    def test_clean_text_handles_empty_string(self):
        """空文字列の処理テスト"""
        result = clean_text("")
        assert result == ""
    
    def test_clean_text_preserves_japanese(self):
        """日本語文字の保持テスト"""
        text = "漢字ひらがなカタカナ"
        result = clean_text(text)
        assert result == "漢字ひらがなカタカナ"


class TestSectionExtraction:
    """セクション抽出機能のテスト"""
    
    def test_extract_section_finds_article_number(self):
        """条文番号の抽出テスト"""
        text = "第1条 これは条文です"
        result = extract_section(text)
        assert result == "第1条"
    
    def test_extract_section_finds_chapter(self):
        """章番号の抽出テスト"""
        text = "第一章 総則"
        result = extract_section(text)
        assert result == "第一章"
    
    def test_extract_section_finds_numbered_heading(self):
        """番号付き見出しの抽出テスト"""
        text = "1.1 概要について"
        result = extract_section(text)
        assert "1.1" in result
    
    def test_extract_section_returns_none_for_no_match(self):
        """セクションが見つからない場合のテスト"""
        text = "これは普通のテキストです"
        result = extract_section(text)
        assert result is None


class TestPageRecord:
    """PageRecordデータクラスのテスト"""
    
    def test_page_record_creation(self):
        """PageRecordの作成テスト"""
        record = PageRecord(
            file_name="test.pdf",
            file_path="/path/to/test.pdf",
            page_no=1,
            text="テキスト",
            section="第1条"
        )
        assert record.file_name == "test.pdf"
        assert record.page_no == 1
        assert record.text == "テキスト"
        assert record.section == "第1条"
    
    def test_page_record_with_none_section(self):
        """セクションがNoneのPageRecordテスト"""
        record = PageRecord(
            file_name="test.pdf",
            file_path="/path/to/test.pdf",
            page_no=1,
            text="テキスト",
            section=None
        )
        assert record.section is None