.PHONY: help install dev lint format test clean index docker-build docker-run

# デフォルトターゲット
help:
	@echo "利用可能なコマンド:"
	@echo "  make install    - 依存パッケージのインストール"
	@echo "  make dev        - 開発サーバーの起動"
	@echo "  make lint       - コードのリント実行"
	@echo "  make format     - コードのフォーマット"
	@echo "  make test       - テストの実行"
	@echo "  make index      - PDFインデックスの作成"
	@echo "  make clean      - 一時ファイルの削除"
	@echo "  make docker-build - Dockerイメージのビルド"
	@echo "  make docker-run   - Dockerコンテナの起動"

# 依存パッケージのインストール
install:
	pip install -r requirements.txt
	cp .env.example .env
	@echo "✅ インストール完了"
	@echo "📝 .envファイルを編集してパスワードを設定してください"

# 開発サーバーの起動
dev:
	streamlit run app.py --server.port 8501 --server.address localhost

# リント実行
lint:
	ruff check .

# コードフォーマット
format:
	black .
	ruff check --fix .

# テスト実行
test:
	pytest tests/ -v

# 簡易テスト（詳細出力なし）
test-quiet:
	pytest tests/ -q

# PDFインデックスの作成
index:
	python -m pdf.ingest

# 一時ファイルの削除
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ 2>/dev/null || true

# Dockerイメージのビルド
docker-build:
	docker build -t internal-chatbot:latest .

# Dockerコンテナの起動
docker-run:
	docker run -p 8501:8501 \
		-v $(PWD)/data/pdfs:/app/data/pdfs:ro \
		-v $(PWD)/.env:/app/.env:ro \
		--name internal-chatbot \
		--rm \
		internal-chatbot:latest

# 全体のチェック（CI用）
check: lint test
	@echo "✅ All checks passed!"