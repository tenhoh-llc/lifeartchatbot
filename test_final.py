#!/usr/bin/env python3
"""
最終動作確認テストスクリプト
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pdf.advanced_search import smart_search
from pdf.intelligent_answer import generate_intelligent_answer
from core.config import AppConfig

def test_query(query, context=None):
    """クエリをテスト"""
    config = AppConfig.load()
    
    print(f"\n{'='*60}")
    print(f"質問: {query}")
    if context:
        print(f"文脈: {context}")
    print(f"{'='*60}")
    
    # スマート検索を実行
    hits = smart_search(
        query=query,
        top_k=5,
        index_path=config.index_path,
        context=context
    )
    
    print(f"\n検索結果: {len(hits)}件")
    
    if hits:
        # 上位3件を表示
        for i, hit in enumerate(hits[:3], 1):
            print(f"  {i}. {hit.file_name} - ページ {hit.page_no} (スコア: {hit.score:.1f})")
        
        # 回答を生成
        print(f"\n生成された回答:")
        print("-" * 40)
        answer = generate_intelligent_answer(query, hits, context)
        print(answer)
        print("-" * 40)
    else:
        print("該当する情報が見つかりませんでした")

if __name__ == "__main__":
    # テストケース
    test_cases = [
        ("育休の条件は？", None),
        ("育児休業が取れない場合はどんな時？", "育休の条件は？"),
        ("有給休暇の繰越はできますか？", None),
        ("パートタイマーの労働時間は？", None),
        ("時間外労働の上限は？", None),
    ]
    
    print("最終動作確認テスト")
    print("=" * 60)
    
    for query, context in test_cases:
        test_query(query, context)