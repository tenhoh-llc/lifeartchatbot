#!/usr/bin/env python3
"""
検索機能のテストスクリプト
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pdf.search import extract_keywords, search
from pdf.advanced_search import smart_search
from pdf.index import get_all_pages
from core.config import AppConfig

def test_search():
    """検索機能をテスト"""
    config = AppConfig.load()
    
    queries = [
        "育休の条件は？",
        "育児休業の条件は？",
        "有給休暇について教えてください",
        "時間外労働について教えて",
        "パートタイマーの労働時間は？"
    ]
    
    for query in queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        
        # キーワード抽出のテスト
        keywords = extract_keywords(query)
        print(f"Extracted keywords: {keywords}")
        
        # 通常の検索
        print("\n[Normal Search]")
        results = search(query, top_k=3, index_path=config.index_path)
        print(f"Results: {len(results)} found")
        for i, hit in enumerate(results[:3], 1):
            print(f"  {i}. {hit.file_name} (page {hit.page_no}, score: {hit.score:.1f})")
        
        # スマート検索
        print("\n[Smart Search]")
        smart_results = smart_search(query, top_k=3, index_path=config.index_path)
        print(f"Results: {len(smart_results)} found")
        for i, hit in enumerate(smart_results[:3], 1):
            print(f"  {i}. {hit.file_name} (page {hit.page_no}, score: {hit.score:.1f})")

def test_index():
    """インデックスの状態を確認"""
    config = AppConfig.load()
    
    print(f"\nIndex path: {config.index_path}")
    print(f"Index exists: {config.index_path.exists()}")
    
    if config.index_path.exists():
        pages = get_all_pages(config.index_path)
        print(f"Total pages in index: {len(pages)}")
        
        # ファイルごとにカウント
        files = {}
        for file_name, page_no, text, section, file_path in pages:
            if file_name not in files:
                files[file_name] = 0
            files[file_name] += 1
        
        print("\nFiles in index:")
        for file_name, count in sorted(files.items()):
            print(f"  - {file_name}: {count} pages")

if __name__ == "__main__":
    print("Testing search functionality...")
    test_index()
    test_search()