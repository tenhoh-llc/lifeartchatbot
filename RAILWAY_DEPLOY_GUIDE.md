# 🚂 Railway デプロイガイド

## 📋 前提条件

- Railwayアカウント（[railway.app](https://railway.app)で作成）
- GitHubアカウント（コードをGitHubにプッシュ済み）
- ローカルでアプリケーションが正常動作していること

## 🎯 デプロイ手順

### 1. プロジェクトの準備

#### 1.1 必要なファイルの作成

**railway.toml** を作成:
```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

**Procfile** を作成（バックアップ用）:
```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true
```

**runtime.txt** を作成:
```
python-3.11.9
```

#### 1.2 .env.example の確認
```env
# 必須設定
APP_PASSWORD=your_secure_password_here

# PDF設定
PDF_DIR=./ライフアート株式会社就業規則PDF
INDEX_PATH=./data/index.sqlite

# ログ設定
LOG_LEVEL=INFO

# LLM設定（使用しない場合はnoneのまま）
LLM_PROVIDER=none
LLM_API_KEY=

# タイムゾーン
TZ=Asia/Tokyo
```

### 2. GitHubリポジトリの準備

```bash
# .gitignoreに以下を追加
echo "*.sqlite" >> .gitignore
echo ".env" >> .gitignore
echo "logs/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "venv/" >> .gitignore

# コミット
git add .
git commit -m "Add Railway deployment configuration"
git push origin main
```

### 3. Railwayでのデプロイ

#### 3.1 新規プロジェクト作成

1. [Railway Dashboard](https://railway.app/dashboard)にアクセス
2. 「New Project」をクリック
3. 「Deploy from GitHub repo」を選択
4. GitHubアカウントを連携（初回のみ）
5. リポジトリを選択

#### 3.2 環境変数の設定

Railwayダッシュボードで以下の環境変数を設定:

| 変数名 | 値 | 説明 |
|--------|-----|------|
| `APP_PASSWORD` | `your_secure_password` | アプリのパスワード（必須） |
| `PDF_DIR` | `./ライフアート株式会社就業規則PDF` | PDFディレクトリ |
| `INDEX_PATH` | `./data/index.sqlite` | インデックスパス |
| `LOG_LEVEL` | `INFO` | ログレベル |
| `TZ` | `Asia/Tokyo` | タイムゾーン |
| `PORT` | （Railwayが自動設定） | ポート番号 |

#### 3.3 PDFファイルのアップロード

**重要**: PDFファイルをGitリポジトリに含める必要があります。

```bash
# PDFディレクトリをGitに追加（機密性に注意）
git add -f ライフアート株式会社就業規則PDF/
git commit -m "Add PDF files for deployment"
git push origin main
```

⚠️ **セキュリティ警告**: 
- 機密性の高いPDFファイルはプライベートリポジトリを使用
- または、外部ストレージ（S3等）から読み込む実装を検討

### 4. ビルド設定の調整

#### 4.1 Nixpacksビルド設定

Railway は自動的に `requirements.txt` を検出してビルドします。

必要に応じて `nixpacks.toml` を作成:
```toml
[phases.setup]
nixPkgs = ["python311", "gcc"]

[phases.install]
cmds = ["pip install -r requirements.txt"]

[start]
cmd = "streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"
```

### 5. デプロイの実行

1. GitHubにプッシュすると自動デプロイが開始
2. Railwayダッシュボードでビルドログを確認
3. デプロイ完了後、生成されたURLにアクセス

### 6. 初回セットアップ

デプロイ後の初回アクセス時:

1. アプリケーションURLにアクセス
2. 設定したパスワードでログイン
3. サイドバーの「インデックス再構築」をクリック
4. PDFのインデックス作成を待つ（初回のみ）

## 🔧 トラブルシューティング

### ポートエラー
```
Error: Streamlit requires raw HTTP connection
```
**解決策**: `railway.toml` の startCommand を確認

### メモリ不足
```
Error: Process running out of memory
```
**解決策**: 
- Railwayのプラン（Hobby以上）にアップグレード
- PDFファイルサイズを最適化

### PDFファイルが見つからない
```
Error: PDF directory not found
```
**解決策**:
- PDFディレクトリがGitリポジトリに含まれているか確認
- 環境変数 `PDF_DIR` のパスを確認

### タイムアウトエラー
```
Error: Application failed to respond
```
**解決策**:
```toml
# railway.tomlに追加
[deploy]
healthcheckTimeout = 300
```

## 🚀 パフォーマンス最適化

### 1. インデックスの永続化

SQLiteデータベースをボリュームに保存:

```python
# core/config.py を修正
import os

class AppConfig(BaseModel):
    # Railway永続ボリューム対応
    index_path: Path = Path(os.getenv("INDEX_PATH", "/data/index.sqlite"))
```

Railwayダッシュボード:
1. Settings → Volumes
2. Mount path: `/data`
3. 環境変数: `INDEX_PATH=/data/index.sqlite`

### 2. キャッシュの活用

```python
# app.py に追加
@st.cache_data(ttl=3600)
def cached_search(query: str):
    return search_intelligent(query)
```

### 3. リソース制限の設定

Railway Pro プランの場合:
- Settings → Resources
- Memory: 2GB以上推奨
- CPU: 1 vCPU以上

## 📊 モニタリング

### ログの確認
```bash
# Railway CLI を使用
railway logs
```

### メトリクスの確認
- Railwayダッシュボード → Metrics
- CPU使用率、メモリ使用量、レスポンスタイムを監視

## 🔐 セキュリティ設定

### 1. カスタムドメイン設定
1. Settings → Domains
2. Add Custom Domain
3. CNAMEレコードを設定

### 2. HTTPS強制
- Railwayはデフォルトで HTTPS を使用

### 3. アクセス制限
```python
# 追加のセキュリティ（IP制限等）が必要な場合
# core/auth.py に実装
```

## 📝 デプロイチェックリスト

- [ ] requirements.txt が最新
- [ ] railway.toml を作成
- [ ] 環境変数を設定（特にAPP_PASSWORD）
- [ ] PDFファイルをリポジトリに追加（またはストレージ設定）
- [ ] .gitignore を確認
- [ ] GitHubにプッシュ
- [ ] Railwayでビルド成功を確認
- [ ] アプリケーションにアクセス可能
- [ ] ログイン機能が動作
- [ ] インデックス再構築が成功
- [ ] 検索機能が正常動作

## 🆘 サポート

問題が発生した場合:
1. [Railway ドキュメント](https://docs.railway.app)
2. [Streamlit デプロイガイド](https://docs.streamlit.io/deploy)
3. ビルドログとランタイムログを確認

## 💰 コスト見積もり

Railway料金（2024年現在）:
- **Developer Plan**: $5/月
  - 500時間の実行時間
  - 8GB RAM、8 vCPU
- **Team Plan**: $20/月/シート
  - 無制限の実行時間
  - より多くのリソース

推奨: まずDeveloper Planで開始し、必要に応じてアップグレード

---

## 🎉 デプロイ完了！

デプロイが成功したら:
1. URLを社内に共有
2. パスワードを安全に管理
3. 定期的にログを確認
4. 必要に応じてPDFを更新