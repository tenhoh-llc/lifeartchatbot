"""
高精度社内チャットボット メインアプリケーション
検索精度とコンテキスト理解を強化したバージョン
"""
import streamlit as st
from pathlib import Path
import os
import sys
from datetime import datetime
from typing import Optional, List, Dict

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from core.config import AppConfig
from core.auth import SimpleAuth
from core.logging import setup_logging, get_logger
from core.query_analyzer import QueryAnalyzer, QueryIntent
from core.better_answer import BetterAnswerGenerator, StructuredAnswer, format_answer_for_display
from pdf.ingest import ingest_directory
from pdf.advanced_search import AdvancedSearchEngine, SearchResult
from pdf.index import get_statistics, get_metadata


# ページ設定
st.set_page_config(
    page_title="社内AIアシスタント",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    /* 回答カードのスタイル */
    .answer-card {
        background-color: #f0f8ff;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #0066cc;
        margin-bottom: 1rem;
    }
    
    /* 根拠カードのスタイル */
    .evidence-card {
        background-color: #f9f9f9;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #ddd;
        margin-bottom: 0.5rem;
    }
    
    /* ハイライトスタイル */
    .highlight {
        background-color: #ffeb3b;
        padding: 2px 4px;
        border-radius: 3px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """セッション状態の初期化"""
    # 基本設定
    if "config" not in st.session_state:
        try:
            st.session_state.config = AppConfig.load()
        except ValueError as e:
            st.error(f"設定エラー: {e}")
            st.stop()
    
    # 認証
    if "auth" not in st.session_state:
        st.session_state.auth = SimpleAuth(st.session_state.config.app_password)
    
    # クエリ解析器
    if "query_analyzer" not in st.session_state:
        st.session_state.query_analyzer = QueryAnalyzer()
    
    # 回答生成器
    if "answer_generator" not in st.session_state:
        st.session_state.answer_generator = BetterAnswerGenerator()
    
    # 検索エンジン
    if "search_engine" not in st.session_state:
        if st.session_state.config.index_path.exists():
            st.session_state.search_engine = AdvancedSearchEngine(
                st.session_state.config.index_path
            )
        else:
            st.session_state.search_engine = None
    
    # チャット履歴
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # 会話コンテキスト
    if "conversation_context" not in st.session_state:
        st.session_state.conversation_context = []


def render_header():
    """ヘッダーのレンダリング"""
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        st.title("🤖 社内AIアシスタント")
        st.caption("高精度PDF検索・回答システム")
    
    with col2:
        if st.session_state.config.index_path.exists():
            stats = get_statistics(st.session_state.config.index_path)
            if stats["total_pages"] > 0:
                st.metric("検索対象", f"{stats['total_pages']:,}ページ")
    
    with col3:
        if st.session_state.auth.is_authenticated():
            if st.button("ログアウト", type="secondary"):
                st.session_state.auth.logout()
                st.rerun()


def render_sidebar():
    """サイドバーのレンダリング"""
    with st.sidebar:
        st.header("⚙️ システム管理")
        
        # インデックス情報
        if st.session_state.config.index_path.exists():
            stats = get_statistics(st.session_state.config.index_path)
            
            st.subheader("📊 データベース状況")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("総ページ数", f"{stats['total_pages']:,}")
            with col2:
                st.metric("PDF数", f"{stats['total_files']:,}")
            
            if stats["last_indexed"]:
                st.caption(f"最終更新: {stats['last_indexed']}")
        else:
            st.warning("⚠️ インデックスが未作成です")
        
        st.divider()
        
        # インデックス管理
        st.subheader("🔄 データベース更新")
        if st.button("PDFを再取り込み", type="primary", use_container_width=True):
            with st.spinner("PDFを解析中..."):
                try:
                    if not st.session_state.config.pdf_dir.exists():
                        st.error(f"PDFディレクトリが存在しません: {st.session_state.config.pdf_dir}")
                        return
                    
                    count = ingest_directory(
                        st.session_state.config.pdf_dir,
                        st.session_state.config.index_path
                    )
                    
                    if count > 0:
                        st.success(f"✅ {count}ページを取り込みました")
                        # 検索エンジンを再初期化
                        st.session_state.search_engine = AdvancedSearchEngine(
                            st.session_state.config.index_path
                        )
                        st.balloons()
                    else:
                        st.warning("PDFファイルが見つかりませんでした")
                        
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")
        
        st.divider()
        
        # 検索設定
        st.subheader("🔍 検索設定")
        st.session_state.search_top_k = st.slider(
            "検索結果数",
            min_value=3,
            max_value=10,
            value=5,
            help="取得する検索結果の最大数"
        )
        
        st.session_state.use_context = st.checkbox(
            "会話履歴を考慮",
            value=True,
            help="前の会話内容を検索に活用します"
        )
        
        st.divider()
        
        # 使い方
        with st.expander("📖 使い方ガイド"):
            st.markdown("""
            ### 🎯 効果的な質問方法
            
            **良い例:**
            - 「有給休暇の繰越について教えてください」
            - 「育児休業の申請手続きは？」
            - 「残業代の計算方法を知りたい」
            
            **ポイント:**
            - 具体的なキーワードを含める
            - 一度に1つの質問をする
            - 続けて質問すると文脈を理解します
            """)
        
        # 会話履歴クリア
        st.divider()
        if st.button("🗑️ 会話履歴をクリア", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.conversation_context = []
            st.session_state.query_analyzer = QueryAnalyzer()
            st.rerun()


def render_chat_message(message: Dict):
    """チャットメッセージのレンダリング"""
    if message["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])
    
    elif message["role"] == "assistant":
        with st.chat_message("assistant", avatar="🤖"):
            if "answer" in message:
                # 構造化された回答
                answer = message["answer"]
                
                if isinstance(answer, StructuredAnswer):
                    # 改良版の構造化回答
                    # メイン回答
                    st.markdown(f"### 📝 回答")
                    st.markdown(f"**{answer.main_answer}**")
                    
                    # 詳細ポイント
                    if answer.details:
                        st.markdown("#### 📋 詳細情報")
                        for detail in answer.details:
                            st.markdown(f"• {detail}")
                    
                    # 根拠
                    if answer.evidence:
                        with st.expander("🔍 根拠となる規程文書の記載を見る"):
                            st.markdown(answer.evidence)
                    
                    # 出典と確信度
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if answer.source:
                            st.caption(f"📚 出典: {answer.source}")
                    with col2:
                        confidence_emoji = "🟢" if answer.confidence > 0.7 else "🟡" if answer.confidence > 0.4 else "🔴"
                        st.caption(f"{confidence_emoji} 確信度: {answer.confidence:.0%}")
                else:
                    # 旧版の回答形式（互換性のため）
                    st.markdown(format_answer_for_display(answer))
            else:
                # 通常のメッセージ
                st.markdown(message.get("content", ""))


def process_query(query: str):
    """クエリを処理して回答を生成"""
    # 検索エンジンが初期化されていない場合
    if st.session_state.search_engine is None:
        return {
            "role": "assistant",
            "content": "⚠️ インデックスが作成されていません。サイドバーから「PDFを再取り込み」を実行してください。"
        }
    
    try:
        # クエリ解析
        context = st.session_state.conversation_context if st.session_state.use_context else None
        query_intent = st.session_state.query_analyzer.analyze(query, context)
        
        # 検索実行
        search_results = st.session_state.search_engine.search(
            query_intent,
            top_k=st.session_state.search_top_k
        )
        
        # 改良された回答生成
        answer = st.session_state.answer_generator.generate(
            query,
            search_results
        )
        
        # 会話履歴に追加
        st.session_state.query_analyzer.add_to_context(query)
        st.session_state.conversation_context.append(query)
        
        return {
            "role": "assistant",
            "answer": answer,
            "search_results": search_results
        }
        
    except Exception as e:
        logger.error(f"Query processing error: {e}")
        return {
            "role": "assistant",
            "content": f"⚠️ エラーが発生しました: {str(e)}"
        }


def render_chat_interface():
    """チャットインターフェースのレンダリング"""
    st.header("💬 AIアシスタントに質問する")
    
    # 初回メッセージ
    if not st.session_state.chat_history:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown("""
            こんにちは！社内規程について何でもお聞きください。
            
            **質問例：**
            - 有給休暇は何日まで繰り越せますか？
            - 育児休業の申請方法を教えてください
            - 残業時間の上限はありますか？
            """)
    
    # チャット履歴を表示
    for message in st.session_state.chat_history:
        render_chat_message(message)
    
    # 入力欄
    query = st.chat_input(
        "質問を入力してください...",
        key="chat_input"
    )
    
    if query:
        # ユーザーメッセージを追加
        st.session_state.chat_history.append({
            "role": "user",
            "content": query
        })
        
        # 回答生成
        with st.spinner("回答を生成中..."):
            response = process_query(query)
            st.session_state.chat_history.append(response)
        
        # ページ再読み込み
        st.rerun()


def main():
    """メイン処理"""
    # 初期化
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
    
    # 認証
    if not st.session_state.auth.is_authenticated():
        st.session_state.auth.render_login_form()
        return
    
    # UI構築
    render_header()
    render_sidebar()
    render_chat_interface()
    
    # フッター
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.caption("© 2024 社内AIアシスタント v2.0.0 - 高精度版")


if __name__ == "__main__":
    main()