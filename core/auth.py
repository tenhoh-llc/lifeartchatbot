"""
認証モジュール
Streamlitのセッション管理を使った単一パスワード認証
"""
import streamlit as st
import hashlib
import time
from typing import Optional
from loguru import logger


class SimpleAuth:
    """
    シンプルなパスワード認証クラス
    
    Streamlitのセッション状態を使用して:
    - 認証状態の管理
    - ログイン試行回数の追跡
    - 一時的なアカウントロック
    """
    
    def __init__(self, password: str, max_attempts: int = 3, lockout_duration: int = 300):
        """
        Args:
            password: 認証用パスワード
            max_attempts: 最大試行回数
            lockout_duration: ロックアウト時間（秒）
        """
        self.password_hash = self._hash_password(password)
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration
        
        # セッション状態の初期化
        self._init_session_state()
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """
        パスワードをハッシュ化
        本番環境ではbcryptなどを使用することを推奨
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _init_session_state(self):
        """
        Streamlitのセッション状態を初期化
        """
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False
        if "login_attempts" not in st.session_state:
            st.session_state.login_attempts = 0
        if "lockout_until" not in st.session_state:
            st.session_state.lockout_until = 0
    
    def is_authenticated(self) -> bool:
        """
        現在の認証状態を確認
        """
        return st.session_state.authenticated
    
    def is_locked_out(self) -> bool:
        """
        アカウントがロックアウトされているか確認
        """
        if st.session_state.lockout_until > time.time():
            return True
        # ロックアウト期間が終了したらカウンタをリセット
        if st.session_state.lockout_until > 0:
            st.session_state.login_attempts = 0
            st.session_state.lockout_until = 0
        return False
    
    def get_remaining_lockout_time(self) -> int:
        """
        残りのロックアウト時間を秒で返す
        """
        remaining = int(st.session_state.lockout_until - time.time())
        return max(0, remaining)
    
    def authenticate(self, password: str) -> bool:
        """
        パスワードを検証して認証
        
        Args:
            password: 入力されたパスワード
        
        Returns:
            認証成功の場合True
        """
        # ロックアウトチェック
        if self.is_locked_out():
            logger.warning("Authentication attempt during lockout period")
            return False
        
        # パスワード検証
        input_hash = self._hash_password(password)
        if input_hash == self.password_hash:
            st.session_state.authenticated = True
            st.session_state.login_attempts = 0
            logger.info("Authentication successful")
            return True
        else:
            st.session_state.login_attempts += 1
            logger.warning(f"Authentication failed. Attempt {st.session_state.login_attempts}/{self.max_attempts}")
            
            # 最大試行回数に達したらロックアウト
            if st.session_state.login_attempts >= self.max_attempts:
                st.session_state.lockout_until = time.time() + self.lockout_duration
                logger.warning(f"Account locked out for {self.lockout_duration} seconds")
            
            return False
    
    def logout(self):
        """
        ログアウト処理
        """
        st.session_state.authenticated = False
        logger.info("User logged out")
    
    def render_login_form(self) -> Optional[bool]:
        """
        ログインフォームを表示
        
        Returns:
            認証成功時True、失敗時False、未入力時None
        """
        st.title("🔐 ログイン")
        
        # ロックアウト中の表示
        if self.is_locked_out():
            remaining = self.get_remaining_lockout_time()
            st.error(
                f"ログイン試行回数が上限に達しました。"
                f"{remaining}秒後に再試行してください。"
            )
            # 自動リロード用のプレースホルダー
            time.sleep(1)
            st.rerun()
            return None
        
        # ログインフォーム
        with st.form("login_form"):
            password = st.text_input(
                "パスワード",
                type="password",
                placeholder="パスワードを入力してください",
                help="管理者から提供されたパスワードを入力"
            )
            
            col1, col2 = st.columns([1, 3])
            with col1:
                submit = st.form_submit_button("ログイン", type="primary", use_container_width=True)
            
            if submit:
                if not password:
                    st.error("パスワードを入力してください")
                    return False
                
                if self.authenticate(password):
                    st.success("ログインに成功しました！")
                    st.rerun()
                    return True
                else:
                    attempts_left = self.max_attempts - st.session_state.login_attempts
                    if attempts_left > 0:
                        st.error(
                            f"パスワードが正しくありません。"
                            f"（残り{attempts_left}回）"
                        )
                    else:
                        st.error("ログイン試行回数が上限に達しました。")
                    return False
        
        # 残り試行回数の表示
        if st.session_state.login_attempts > 0:
            attempts_left = self.max_attempts - st.session_state.login_attempts
            if attempts_left > 0:
                st.info(f"ログイン可能回数: 残り{attempts_left}回")
        
        return None


def check_auth(password: str) -> bool:
    """
    認証チェックのヘルパー関数（後方互換性のため）
    
    Args:
        password: 環境変数から取得したパスワード
    
    Returns:
        認証済みの場合True
    """
    auth = SimpleAuth(password)
    
    if auth.is_authenticated():
        return True
    
    # ログインフォームを表示
    auth.render_login_form()
    return False