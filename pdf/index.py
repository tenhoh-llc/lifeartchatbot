"""
インデックス管理モジュール
SQLiteデータベースへのページデータの保存と取得
"""
import sqlite3
from pathlib import Path
from typing import Iterable, List, Tuple, Optional
from contextlib import contextmanager
from loguru import logger
from .ingest import PageRecord


@contextmanager
def get_db_connection(index_path: Path):
    """
    データベース接続のコンテキストマネージャー
    
    with文を使用することで:
    - 自動的に接続がクローズされる
    - エラー時も適切にクリーンアップ
    - トランザクション管理
    """
    conn = None
    try:
        # データベースに接続
        conn = sqlite3.connect(index_path)
        # Row factoryを設定（辞書形式でアクセス可能に）
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def ensure_schema(db: sqlite3.Connection):
    """
    データベーススキーマを作成
    
    Args:
        db: データベース接続
    
    SQLiteの特徴:
    - ファイルベースのデータベース
    - 軽量で高速
    - SQLのサブセットをサポート
    """
    schema_sql = """
    -- ページデータを格納するテーブル
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自動採番のID
        file_name TEXT NOT NULL,               -- PDFファイル名
        file_path TEXT NOT NULL,               -- PDFファイルのパス
        page_no INTEGER NOT NULL,              -- ページ番号
        text TEXT NOT NULL,                    -- 抽出したテキスト
        section TEXT,                          -- セクション名（NULL可）
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,  -- 作成日時
        UNIQUE(file_name, page_no)             -- ファイル名とページ番号の組み合わせは一意
    );
    
    -- 検索用インデックス
    CREATE INDEX IF NOT EXISTS idx_pages_file ON pages(file_name);
    CREATE INDEX IF NOT EXISTS idx_pages_text ON pages(text);
    
    -- メタデータテーブル（インデックス情報など）
    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    try:
        db.executescript(schema_sql)
        db.commit()
        logger.debug("Database schema ensured")
    except Exception as e:
        logger.error(f"Failed to create schema: {e}")
        raise


def upsert_pages(index_path: Path, pages: Iterable[PageRecord]):
    """
    ページデータをデータベースに保存（UPSERT）
    
    Args:
        index_path: データベースファイルのパス
        pages: 保存するページレコードのリスト
    
    UPSERT処理:
    - 既存のレコードは更新
    - 新規のレコードは挿入
    """
    with get_db_connection(index_path) as db:
        # スキーマを確認
        ensure_schema(db)
        
        cursor = db.cursor()
        
        # トランザクション開始
        db.execute("BEGIN TRANSACTION")
        
        try:
            # 既存データをクリア（簡易実装）
            # 本番環境では差分更新を実装することを推奨
            cursor.execute("DELETE FROM pages")
            
            # バッチ挿入（高速化のため）
            insert_sql = """
            INSERT INTO pages (file_name, file_path, page_no, text, section)
            VALUES (?, ?, ?, ?, ?)
            """
            
            # データを準備
            data = [
                (p.file_name, p.file_path, p.page_no, p.text, p.section)
                for p in pages
            ]
            
            # バッチ実行
            cursor.executemany(insert_sql, data)
            
            # メタデータを更新
            cursor.execute("""
                INSERT OR REPLACE INTO metadata (key, value)
                VALUES ('last_indexed', datetime('now'))
            """)
            
            # コミット
            db.commit()
            
            logger.info(f"Upserted {len(data)} pages to database")
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to upsert pages: {e}")
            raise


def get_all_pages(index_path: Path) -> List[Tuple]:
    """
    データベースから全ページを取得
    
    Args:
        index_path: データベースファイルのパス
    
    Returns:
        ページデータのタプルのリスト
    """
    pages = []
    
    with get_db_connection(index_path) as db:
        cursor = db.execute("""
            SELECT file_name, page_no, text, section, file_path
            FROM pages
            ORDER BY file_name, page_no
        """)
        
        for row in cursor:
            pages.append(tuple(row))
    
    return pages


def search_pages(
    index_path: Path,
    query: str,
    limit: int = 10
) -> List[sqlite3.Row]:
    """
    簡易テキスト検索
    
    Args:
        index_path: データベースファイルのパス
        query: 検索クエリ
        limit: 最大取得件数
    
    Returns:
        検索結果のリスト
    
    注意:
    - SQLiteのLIKE演算子を使用した簡易検索
    - 本番環境ではFTS（Full Text Search）の使用を推奨
    """
    results = []
    
    with get_db_connection(index_path) as db:
        # エスケープ処理
        escaped_query = query.replace("%", "\\%").replace("_", "\\_")
        
        cursor = db.execute("""
            SELECT 
                file_name,
                page_no,
                text,
                section,
                file_path,
                -- 簡易スコアリング（クエリが出現する位置）
                CASE 
                    WHEN section LIKE ? THEN 100
                    WHEN text LIKE ? THEN 50
                    ELSE 0
                END as score
            FROM pages
            WHERE text LIKE ? OR section LIKE ?
            ORDER BY score DESC, file_name, page_no
            LIMIT ?
        """, (
            f"%{escaped_query}%",  # section用
            f"%{escaped_query}%",  # text用（スコアリング）
            f"%{escaped_query}%",  # WHERE句用
            f"%{escaped_query}%",  # WHERE句用（section）
            limit
        ))
        
        results = list(cursor)
    
    return results


def get_metadata(index_path: Path, key: str) -> Optional[str]:
    """
    メタデータを取得
    
    Args:
        index_path: データベースファイルのパス
        key: メタデータのキー
    
    Returns:
        メタデータの値（存在しない場合はNone）
    """
    with get_db_connection(index_path) as db:
        cursor = db.execute(
            "SELECT value FROM metadata WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        return row["value"] if row else None


def get_statistics(index_path: Path) -> dict:
    """
    インデックスの統計情報を取得
    
    Args:
        index_path: データベースファイルのパス
    
    Returns:
        統計情報の辞書
    """
    stats = {
        "total_pages": 0,
        "total_files": 0,
        "last_indexed": None,
        "average_text_length": 0
    }
    
    with get_db_connection(index_path) as db:
        # 総ページ数
        cursor = db.execute("SELECT COUNT(*) as count FROM pages")
        stats["total_pages"] = cursor.fetchone()["count"]
        
        # ファイル数
        cursor = db.execute("SELECT COUNT(DISTINCT file_name) as count FROM pages")
        stats["total_files"] = cursor.fetchone()["count"]
        
        # 平均テキスト長
        cursor = db.execute("SELECT AVG(LENGTH(text)) as avg_len FROM pages")
        result = cursor.fetchone()
        stats["average_text_length"] = int(result["avg_len"]) if result["avg_len"] else 0
        
        # 最終インデックス日時
        stats["last_indexed"] = get_metadata(index_path, "last_indexed")
    
    return stats