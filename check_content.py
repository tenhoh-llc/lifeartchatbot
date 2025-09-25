#!/usr/bin/env python3
"""
PDFの実際の内容を確認するスクリプト
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pdf.advanced_search import smart_search
from core.config import AppConfig

config = AppConfig.load()

# 育休の条件を検索
query = "育休の条件は？"
hits = smart_search(query, top_k=1, index_path=config.index_path)

if hits:
    hit = hits[0]
    print(f"File: {hit.file_name}")
    print(f"Page: {hit.page_no}")
    print(f"Score: {hit.score}")
    print("\n" + "="*60)
    print("Text content (first 1000 chars):")
    print("="*60)
    print(hit.text[:1000])
    print("\n" + "="*60)
    print("Full text length:", len(hit.text))