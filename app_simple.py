"""
社内チャットボット シンプル版
READMEの仕様通り、PDFの該当ページ抜粋+出典を返す
"""
import streamlit as st
from pathlib import Path
import sys

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from core.config import AppConfig
from core.auth import SimpleAuth
from core.logging import setup_logging, get_logger
from pdf.ingest import ingest_directory
from pdf.search_enhanced import search_enhanced, extract_smart_snippet
from pdf.index import get_statistics


# ページ設定
st.set_page_config(
    page_title="社内チャットボット",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_session_state():
    """セッション状態の初期化"""
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
    """ヘッダー表示"""
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        st.title("📚 社内チャットボット")
        st.caption("ライフアート株式会社 就業規則検索システム")
    
    with col2:
        if st.session_state.config.index_path.exists():
            stats = get_statistics(st.session_state.config.index_path)
            if stats["total_pages"] > 0:
                st.metric("検索対象", f"{stats['total_pages']}ページ")
    
    with col3:
        if st.session_state.auth.is_authenticated():
            if st.button("ログアウト"):
                st.session_state.auth.logout()
                st.rerun()


def render_sidebar():
    """サイドバー表示"""
    with st.sidebar:
        st.header("⚙️ 管理")
        
        # インデックス情報
        if st.session_state.config.index_path.exists():
            stats = get_statistics(st.session_state.config.index_path)
            st.info(f"""
            📊 **データベース状況**
            - 総ページ数: {stats['total_pages']}
            - PDFファイル数: {stats['total_files']}
            """)
        
        # インデックス再構築
        if st.button("🔄 インデックス再構築", use_container_width=True):
            with st.spinner("PDFを処理中..."):
                try:
                    count = ingest_directory(
                        st.session_state.config.pdf_dir,
                        st.session_state.config.index_path
                    )
                    st.success(f"✅ {count}ページをインデックスしました")
                except Exception as e:
                    st.error(f"エラー: {e}")
        
        st.divider()
        
        # 使い方
        with st.expander("📖 使い方"):
            st.markdown("""
            1. 質問を入力（例: 有給休暇、育児休業、パート勤務時間）
            2. 該当箇所が抜粋表示されます
            3. 出典（ファイル名・ページ番号）を確認できます
            """)
        
        # 利用可能なPDF
        st.divider()
        st.caption("""
        **利用可能なPDF:**
        - パートタイマー規程
        - 育児介護休業規程
        - 育児介護労使協定
        """)


def render_chat():
    """チャットインターフェース"""
    st.header("💬 質問してください")
    
    # チャット履歴表示
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(message["content"])
    
    # 入力欄
    query = st.chat_input("質問を入力...")
    
    if query:
        # ユーザーメッセージを追加
        st.session_state.chat_history.append({
            "role": "user",
            "content": query
        })
        
        # 検索実行
        with st.spinner("検索中..."):
            results = search_enhanced(
                query=query,
                index_path=st.session_state.config.index_path,
                top_k=3
            )
            
            if results:
                # 最も関連性の高い結果を使用
                best_result = results[0]
                
                # 抜粋を生成（マッチした用語も活用）
                snippet = extract_smart_snippet(
                    best_result.text, 
                    query,
                    best_result.matched_terms
                )
                
                # 回答を構築
                response = f"""
### 📄 該当箇所の抜粋

{snippet}

---

**📚 出典情報:**
- **ファイル:** {best_result.file_name}
- **ページ:** {best_result.page_no}
"""
                
                if best_result.section:
                    response += f"- **セクション:** {best_result.section}\n"
                
                # 他の候補も表示
                if len(results) > 1:
                    response += "\n**🔍 その他の候補:**\n"
                    for i, result in enumerate(results[1:], 2):
                        response += f"{i}. {result.file_name} - ページ {result.page_no}\n"
                
            else:
                # 結果なし
                response = """
❌ **該当する情報が見つかりませんでした**

検索のヒント:
- より具体的なキーワードを試してください
- 「有給休暇」「育児休業」「パート」などの用語を使用してください
- 別の表現で検索してみてください
"""
            
            # アシスタントメッセージを追加
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response
            })
        
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
    
    # 認証チェック
    if not st.session_state.auth.is_authenticated():
        st.session_state.auth.render_login_form()
        return
    
    # UI構築
    render_header()
    render_sidebar()
    render_chat()
    
    # フッター
    st.divider()
    st.caption("© 2024 ライフアート株式会社 社内チャットボット v1.0")


if __name__ == "__main__":
    main()