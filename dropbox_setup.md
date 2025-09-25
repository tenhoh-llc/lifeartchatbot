# 📁 Dropboxの就業規則を使う最も簡単な方法

## 🎯 3つの方法（簡単な順）

### 方法1: 手動でPDF変換（最も簡単・確実）
```bash
# Dropboxから.docファイルをダウンロード
1. Dropboxフォルダを開く
2. 就業規則.doc等を選択
3. Word/Googleドキュメントで開く
4. ファイル → PDFとしてエクスポート
5. data/pdfs/ フォルダに保存
6. アプリで「インデックス再構築」
```

**メリット**: 
- 追加インストール不要
- 確実に動作
- レイアウト保持

### 方法2: python-docxで自動読み込み
```bash
# 1. python-docxをインストール
pip install python-docx

# 2. .docxファイルをdata/pdfs/にコピー
cp ~/Dropbox/就業規則/*.docx data/pdfs/

# 3. アプリを起動してインデックス再構築
streamlit run app.py
```

**メリット**:
- 自動処理
- 更新が簡単

**注意**:
- 古い.doc形式は非対応（.docxのみ）
- .docは事前に.docxに変換が必要

### 方法3: Dropboxから直接ダウンロード
```python
# urls.txtを作成（Dropbox共有リンクを記載）
https://www.dropbox.com/s/xxxxx/就業規則.docx?dl=0
https://www.dropbox.com/s/yyyyy/給与規程.docx?dl=0
https://www.dropbox.com/s/zzzzz/育児介護規程.docx?dl=0
```

```bash
# Pythonスクリプトで一括ダウンロード
python -c "
from pdf.doc_reader import batch_download_dropbox
from pathlib import Path
batch_download_dropbox(Path('urls.txt'), Path('data/pdfs'))
"
```

## 🔄 .docから.docxへの変換方法

### Windows/Mac
1. Wordで.docファイルを開く
2. ファイル → 名前を付けて保存
3. ファイル形式: Word文書(.docx)

### オンライン変換
1. [Googleドライブ](https://drive.google.com)にアップロード
2. Googleドキュメントで開く
3. ファイル → ダウンロード → Microsoft Word (.docx)

## 📋 必要なパッケージ

```bash
# requirements.txtに追加
python-docx==1.1.0  # Word文書読み込み
requests==2.31.0    # Dropboxダウンロード（既にインストール済み）
```

## 🚀 実際の手順（推奨）

### ステップ1: まずPDF変換を試す
最も確実なので、重要な文書はPDFに変換することを推奨

### ステップ2: 大量にある場合は.docx対応
```bash
# python-docxをインストール
pip install python-docx

# Dropboxから.docxファイルをコピー
cp ~/Dropbox/Company/Rules/*.docx data/pdfs/

# アプリでインデックス再構築
```

### ステップ3: 動作確認
- 「有給休暇」「給与」などで検索
- 正しく内容が表示されるか確認

## ⚠️ トラブルシューティング

### .docファイルが読めない
→ .docxに変換するか、PDFに変換

### 文字化けする
→ PDFに変換して使用

### レイアウトが崩れる
→ PDFに変換して使用（最も確実）

### Dropboxのリンクが機能しない
→ 共有リンクの末尾を`?dl=0`から`?dl=1`に変更

## 💡 ベストプラクティス

1. **重要文書はPDF化**: 確実性を重視
2. **更新頻度が高い文書は.docx**: 自動処理可能
3. **フォルダ整理**: 種類別にフォルダ分け
   ```
   data/pdfs/
   ├── 就業規則/
   ├── 給与規程/
   └── 福利厚生/
   ```

## 📝 まとめ

**一番楽な方法 = WordでPDF変換**

理由：
- 追加インストール不要
- 確実に動作
- レイアウト完璧
- 検索も高速

時間があれば.docx対応を設定すると、今後の更新が楽になります。