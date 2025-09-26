"""
社内チャットボット メインアプリケーション
StreamlitでPDF参照型の質問応答システムを提供
"""
import streamlit as st
from pathlib import Path
import os
import sys
from datetime import datetime
from typing import Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from core.config import AppConfig
from core.auth import SimpleAuth
from core.logging import setup_logging, get_logger
from pdf.ingest import ingest_directory
from pdf.search_intelligent import search_intelligent as search_improved
from pdf.search_intelligent import generate_intelligent_answer as generate_answer_from_hits
from pdf.search_with_llm import search_with_llm, format_search_result
from pdf.snippet import make_snippet
from pdf.index import get_statistics


# ページ設定（最初に実行する必要がある）
st.set_page_config(
    page_title="社内チャットボット",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_session_state():
    """
    セッション状態の初期化
    Streamlitでは状態管理にsession_stateを使用
    """
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "search_history" not in st.session_state:
        st.session_state.search_history = []
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "config" not in st.session_state:
        try:
            st.session_state.config = AppConfig.load()
        except ValueError as e:
            st.error(f"設定エラー: {e}")
            st.stop()
    if "auth" not in st.session_state:
        st.session_state.auth = SimpleAuth(st.session_state.config.app_password)


def render_header():
    """
    ヘッダー部分のレンダリング
    """
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        st.title("📚 社内チャットボット")
        st.caption("PDF規程文書の検索・参照システム")
    
    with col2:
        # インデックス統計
        if st.session_state.config.index_path.exists():
            stats = get_statistics(st.session_state.config.index_path)
            if stats["total_pages"] > 0:
                st.metric("インデックス済みページ", f"{stats['total_pages']:,}")
    
    with col3:
        if st.session_state.auth.is_authenticated():
            if st.button("ログアウト", type="secondary"):
                st.session_state.auth.logout()
                st.rerun()


def render_sidebar():
    """
    サイドバーのレンダリング
    """
    with st.sidebar:
        st.header("⚙️ 管理機能")
        
        # インデックス情報
        if st.session_state.config.index_path.exists():
            stats = get_statistics(st.session_state.config.index_path)
            
            st.subheader("📊 インデックス情報")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("総ページ数", f"{stats['total_pages']:,}")
            with col2:
                st.metric("PDF数", f"{stats['total_files']:,}")
            
            if stats["last_indexed"]:
                st.caption(f"最終更新: {stats['last_indexed']}")
        else:
            st.info("インデックスが未作成です")
        
        st.divider()
        
        # インデックス再構築
        st.subheader("🔄 インデックス管理")
        
        if st.button("インデックス再構築", type="primary", use_container_width=True):
            with st.spinner("PDFを処理中..."):
                try:
                    # PDFディレクトリの確認
                    if not st.session_state.config.pdf_dir.exists():
                        st.error(f"PDFディレクトリが存在しません: {st.session_state.config.pdf_dir}")
                        return
                    
                    # インデックス作成
                    count = ingest_directory(
                        st.session_state.config.pdf_dir,
                        st.session_state.config.index_path
                    )
                    
                    if count > 0:
                        st.success(f"✅ {count}ページをインデックスしました")
                        st.balloons()
                    else:
                        st.warning("PDFファイルが見つかりませんでした")
                        st.info(f"PDFファイルを以下に配置してください:\n{st.session_state.config.pdf_dir}")
                    
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
                    logger.error(f"Indexing failed: {e}")
        
        st.divider()
        
        # 使い方
        with st.expander("📖 使い方"):
            st.markdown("""
            1. **初回セットアップ**
               - PDFファイルを `data/pdfs/` に配置
               - 「インデックス再構築」をクリック
            
            2. **検索方法**
               - キーワードを入力して検索
               - 例: 「有給休暇」「給与」「時短勤務」
            
            3. **結果の見方**
               - 関連度の高い順に表示
               - 該当箇所がハイライト表示
               - ファイル名とページ番号を確認可能
            """)
        
        # 注意事項
        st.divider()
        st.warning("""
        ⚠️ **注意事項**
        - 本システムの回答は参考情報です
        - 正式な確認は原本をご参照ください
        - 法的効力はありません
        """)


def render_search_interface():
    """
    検索インターフェースのレンダリング（チャット形式）
    """
    st.header("💬 チャットボット")
    
    # チャット履歴を表示
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(message["content"])
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    if "answer" in message:
                        st.markdown(message["answer"])
                        if "source" in message:
                            st.caption(f"📌 出典: {message['source']}")
                    else:
                        st.markdown(message["content"])
    
    # 入力欄
    query = st.chat_input(
        "質問を入力してください（例: 有給休暇の繰越について教えてください）",
        key="chat_input"
    )
    
    # 検索実行
    if query:
        # ユーザーメッセージを追加
        st.session_state.chat_history.append({
            "role": "user",
            "content": query
        })
        
        # 履歴に追加
        st.session_state.search_history.append(query)
        
        # 検索処理
        with st.spinner("回答を生成中..."):
            try:
                # 前の会話の文脈を取得（検索用）
                search_context = None
                if len(st.session_state.chat_history) > 1:
                    for msg in reversed(st.session_state.chat_history[:-1]):
                        if msg["role"] == "user":
                            search_context = msg["content"]
                            break

                # LLM統合検索を実行
                result = search_with_llm(
                    query=query,
                    index_path=st.session_state.config.index_path,
                    top_k=5,
                    context=search_context,
                    use_llm=None  # 設定から自動判断
                )

                if result.search_hits:
                    # 整形された回答を表示
                    message_content = format_search_result(result)

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": message_content
                    })
                else:
                    # 該当なしメッセージ
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"""{result.answer}

💡 **検索のヒント:**
- より具体的なキーワードをお試しください
- 別の表現で検索してみてください
- 部分的なキーワードで検索してみてください"""
                    })

            except Exception as e:
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"エラーが発生しました: {e}"
                })
                logger.error(f"Search error: {e}")
        
        # ページを再読み込みして新しいメッセージを表示
        st.rerun()


def render_search_results(query: str, hits):
    """
    検索結果の表示
    
    Args:
        query: 検索クエリ
        hits: 検索結果のリスト
    """
    st.success(f"📋 {len(hits)}件の関連情報が見つかりました")
    
    # タブで結果を整理
    tab1, tab2, tab3 = st.tabs(["💬 回答", "📄 根拠・抜粋", "📊 詳細情報"])
    
    with tab1:
        # Q&A形式の直接回答
        st.markdown("### 質問への回答")
        
        # 直接的な回答を生成
        answer = generate_answer(query, hits, None)
        
        # 回答を見やすく表示
        with st.container():
            st.markdown(answer)
            
            st.divider()
            
            # 出典を小さく表示
            best_hit = hits[0]
            st.caption(f"""
            📌 **根拠:** {best_hit.file_name} - {best_hit.section if best_hit.section else f'ページ {best_hit.page_no}'}
            """)
            
            # 注意書き
            st.info("💡 この回答は規程文書から自動生成されています。正式な確認は原本をご参照ください。")
    
    with tab2:
        # 最も関連性の高い結果
        best_hit = hits[0]
        
        # メイン結果カード
        with st.container():
            st.subheader("根拠となる規程文書の抜粋")
            
            # スニペット生成
            snippet = make_snippet(
                best_hit.text,
                query,
                window=150,
                max_length=500
            )
            
            # 結果表示
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # 抜粋表示（ハイライト付き）
                st.markdown("**📝 該当箇所：**")
                st.markdown(snippet.excerpt)
                
                # 出典情報
                st.caption(f"""
                **出典:** {best_hit.file_name} - ページ {best_hit.page_no}
                {f'**セクション:** {best_hit.section}' if best_hit.section else ''}
                """)
            
            with col2:
                # スコア表示
                score_percentage = min(100, best_hit.score)
                st.metric("関連度スコア", f"{score_percentage:.0f}%")
                
                # ファイルパス（デバッグ用）
                with st.expander("詳細"):
                    st.caption(f"ファイル: {best_hit.file_path}")
        
        st.divider()
        
        # その他の結果
        if len(hits) > 1:
            st.subheader("その他の関連結果")
            
            for i, hit in enumerate(hits[1:], start=2):
                with st.expander(f"{i}. {hit.file_name} - ページ {hit.page_no} (スコア: {hit.score:.0f})"):
                    # スニペット生成
                    snippet = make_snippet(
                        hit.text,
                        query,
                        window=100,
                        max_length=300
                    )
                    
                    st.markdown(snippet.excerpt)
                    
                    if hit.section:
                        st.caption(f"セクション: {hit.section}")
    
    with tab3:
        # 詳細情報タブ
        st.subheader("検索結果の詳細")
        
        # データフレーム形式で表示
        import pandas as pd
        
        results_data = []
        for i, hit in enumerate(hits, start=1):
            results_data.append({
                "順位": i,
                "ファイル": hit.file_name,
                "ページ": hit.page_no,
                "セクション": hit.section or "-",
                "スコア": f"{hit.score:.1f}",
                "テキスト長": len(hit.text)
            })
        
        df = pd.DataFrame(results_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 検索メトリクス
        st.subheader("検索統計")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("検索クエリ長", len(query))
        with col2:
            avg_score = sum(h.score for h in hits) / len(hits)
            st.metric("平均スコア", f"{avg_score:.1f}")
        with col3:
            st.metric("ヒット数", len(hits))


def main():
    """
    メイン処理
    """
    # セッション状態の初期化
    init_session_state()
    
    # ロギング設定
    config = st.session_state.config
    setup_logging(
        log_level=config.log_level,
        log_file=Path("logs/app.log"),
        privacy_mode=True
    )
    
    global logger
    logger = get_logger(__name__)
    
    # 認証チェック
    if not st.session_state.auth.is_authenticated():
        st.session_state.auth.render_login_form()
        return
    
    # ヘッダー
    render_header()
    
    # サイドバー
    render_sidebar()
    
    # メインコンテンツ（チャット形式）
    render_search_interface()
    
    # フッター
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.caption("© 2024 社内チャットボット v1.0.0")


if __name__ == "__main__":
    main()