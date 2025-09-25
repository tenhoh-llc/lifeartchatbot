#!/bin/bash
# ライフアート株式会社チャットボット起動スクリプト

echo "🤖 ライフアート株式会社 社内チャットボット起動中..."

# 仮想環境を有効化
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "⚠️ 仮想環境を作成しています..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# アプリケーション起動
echo "📚 利用可能なPDF:"
echo "  - パートタイマー規程 (19ページ)"
echo "  - 育児介護休業規程 (13ページ)"
echo "  - 育児介護労使協定 (2ページ)"
echo ""
echo "🚀 アプリケーションを起動しています..."
echo "   ブラウザで http://localhost:8501 を開いてください"
echo ""

streamlit run app.py --server.port 8501 --server.address localhost