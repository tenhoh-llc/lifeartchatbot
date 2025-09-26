# LLM（OpenAI）統合機能のセットアップガイド

## 概要

このアプリケーションは、PDF文書の検索結果を基にLLM（Large Language Model）を使用して自然な回答を生成する機能を搭載しています。

## 機能

### 1. ルールベース回答（デフォルト）
- 正規表現パターンマッチングによる回答生成
- LLM APIキー不要
- 高速で安定した動作

### 2. LLM統合回答（OpenAI）
- OpenAI GPTモデルを使用した自然な回答生成
- 検索結果を文脈として利用
- より柔軟で人間らしい回答

## セットアップ手順

### 1. OpenAI APIキーの取得

1. [OpenAI Platform](https://platform.openai.com/)にアクセス
2. アカウントを作成またはログイン
3. [API Keys](https://platform.openai.com/api-keys)ページへ移動
4. 「Create new secret key」をクリック
5. 生成されたAPIキーをコピー（`sk-`で始まる文字列）

### 2. 環境変数の設定

`.env`ファイルを作成し、以下を設定：

```env
# 必須設定
APP_PASSWORD=your_secure_password

# PDF設定
PDF_DIR=./ライフアート株式会社就業規則PDF
INDEX_PATH=./data/index.sqlite

# LLM設定（OpenAI使用時）
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-api-key-here

# その他の設定
LOG_LEVEL=INFO
TZ=Asia/Tokyo
```

### 3. 設定オプション

#### LLMプロバイダー設定

- `LLM_PROVIDER=none`: LLMを使用しない（ルールベース回答のみ）
- `LLM_PROVIDER=openai`: OpenAI GPTモデルを使用

#### モデル選択（コード内で変更可能）

デフォルトは `gpt-4o-mini` を使用。`pdf/llm_answer.py` で変更可能：

```python
model: str = "gpt-4o-mini"  # または "gpt-3.5-turbo", "gpt-4", "gpt-4o"
```

## 使用方法

### 1. アプリケーションの起動

```bash
streamlit run app.py
```

### 2. 質問の入力

通常通り質問を入力すると、設定に応じて：
- LLM有効時：OpenAI GPTが回答を生成
- LLM無効時：ルールベースシステムが回答を生成

### 3. 回答の確認

回答には以下の情報が含まれます：
- 生成された回答
- 関連する文書の抜粋
- 信頼度スコア（高/中/低）
- 使用した方式（AI/ルールベース）
- 出典情報

## テストの実行

LLM機能のテストを実行：

```bash
python test_llm.py
```

テストには以下が含まれます：
- LLMなしでの動作確認
- モックAPIでの統合テスト
- エラー処理の確認

## 料金について

### OpenAI API料金（2024年時点の目安）

- **gpt-4o-mini**:
  - 入力: $0.15 / 1M tokens
  - 出力: $0.6 / 1M tokens
  - 最も経済的で高速

- **gpt-3.5-turbo**:
  - 入力: $0.5 / 1M tokens
  - 出力: $1.5 / 1M tokens

- **gpt-4o**:
  - 入力: $2.5 / 1M tokens
  - 出力: $10 / 1M tokens
  - 最も高性能

### 使用量の目安

- 1回の質問応答：約500-1500 tokens
- 月1000回の利用：約$0.5-2（gpt-4o-miniの場合）

## トラブルシューティング

### LLMが動作しない場合

1. **環境変数の確認**
   ```bash
   echo $LLM_PROVIDER
   echo $LLM_API_KEY
   ```

2. **APIキーの検証**
   - APIキーが正しくコピーされているか確認
   - OpenAIダッシュボードで使用量制限を確認

3. **ログの確認**
   ```bash
   tail -f logs/app.log
   ```

4. **フォールバック動作**
   - API エラー時は自動的にルールベース回答に切り替わります

### パフォーマンスの最適化

1. **キャッシュの活用**
   - 同じ質問は内部でキャッシュされます（15分間）

2. **モデルの選択**
   - 速度重視：`gpt-4o-mini`
   - 品質重視：`gpt-4o`

3. **検索結果の制限**
   - `top_k`パラメータで検索結果数を調整

## セキュリティ上の注意

1. **APIキーの管理**
   - APIキーを直接コードに記述しない
   - `.env`ファイルを`.gitignore`に追加
   - 本番環境では環境変数を使用

2. **アクセス制御**
   - `APP_PASSWORD`で基本的なアクセス制御
   - 本番環境では追加の認証機構を検討

3. **使用量の監視**
   - OpenAIダッシュボードで定期的に使用量を確認
   - 必要に応じて使用量制限を設定

## お問い合わせ

問題が解決しない場合は、以下の情報と共にお問い合わせください：
- エラーメッセージ
- 環境変数の設定（APIキーは除く）
- ログファイルの関連部分