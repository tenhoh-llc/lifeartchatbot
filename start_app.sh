#!/bin/bash
# 高精度チャットボットの起動スクリプト

echo "🤖 社内AIアシスタント 起動準備中..."

# Python仮想環境のチェック
if [ -d "venv" ]; then
    echo "✅ 仮想環境を有効化"
    source venv/bin/activate
else
    echo "⚠️  仮想環境が見つかりません。作成します..."
    python3 -m venv venv
    source venv/bin/activate
fi

# 依存パッケージのインストール
echo "📦 パッケージをチェック中..."
pip install -q -r requirements.txt 2>/dev/null || {
    echo "⚠️  パッケージインストールでエラーが発生しました"
    echo "手動でインストールしてください: pip install -r requirements.txt"
    exit 1
}

# .envファイルのチェック
if [ ! -f ".env" ]; then
    echo "⚠️  .envファイルが見つかりません。作成します..."
    cp .env.example .env
    echo "📝 .envファイルを編集してパスワードを設定してください"
    echo "   編集後、再度このスクリプトを実行してください"
    exit 1
fi

# データディレクトリの作成
mkdir -p data/pdfs logs

echo "🚀 高精度版アプリケーションを起動します..."
echo "   ブラウザで http://localhost:8501 を開いてください"
echo ""

# 高精度版を起動
python3 -m streamlit run app_advanced.py --server.port 8501 --server.address localhost