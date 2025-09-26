"""
LLM統合検索モジュール
検索結果を基にLLMで自然な回答を生成する統合機能
"""
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
from loguru import logger

from .search import search, SearchHit
from .llm_answer import generate_llm_answer
from .intelligent_answer import generate_intelligent_answer
from .snippet import make_snippet
from core.config import AppConfig


@dataclass
class SearchWithLLMResult:
    """
    LLM統合検索の結果
    """
    query: str
    answer: str
    search_hits: List[SearchHit]
    snippet: str
    confidence: str
    sources: List[Dict[str, Any]]
    llm_used: bool


def search_with_llm(
    query: str,
    top_k: int = 5,
    index_path: Path | str = "./data/index.sqlite",
    min_score: float = 30.0,
    context: Optional[str] = None,
    use_llm: Optional[bool] = None
) -> SearchWithLLMResult:
    """
    検索とLLM回答生成を統合した関数

    Args:
        query: 検索クエリ
        top_k: 返す結果の最大数
        index_path: インデックスデータベースのパス
        min_score: 最小スコア閾値
        context: 前の会話の文脈
        use_llm: LLMを使用するか（Noneの場合は設定から判断）

    Returns:
        SearchWithLLMResult: 統合された検索結果
    """
    logger.info(f"Searching with LLM for: {query[:50]}...")

    # 検索を実行
    search_hits = search(
        query=query,
        top_k=top_k,
        index_path=index_path,
        min_score=min_score,
        context=context
    )

    if not search_hits:
        logger.warning("No search results found")
        return SearchWithLLMResult(
            query=query,
            answer="申し訳ございません。該当する情報が見つかりませんでした。別の表現でお尋ねください。",
            search_hits=[],
            snippet="",
            confidence="low",
            sources=[],
            llm_used=False
        )

    # LLM使用の判定
    if use_llm is None:
        # 設定から判断
        try:
            config = AppConfig.load()
            use_llm = config.llm_provider != "none"
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
            use_llm = False

    # 回答を生成
    llm_used = False
    if use_llm:
        try:
            # LLMを使用して回答を生成
            answer = generate_llm_answer(
                query=query,
                search_results=search_hits,
                context=context,
                use_llm=True
            )
            llm_used = True
            logger.info("Answer generated using LLM")
        except Exception as e:
            logger.error(f"Failed to generate LLM answer: {e}")
            # フォールバック：ルールベースの回答生成
            answer = generate_intelligent_answer(query, search_hits, context)
            logger.info("Fallback to rule-based answer generation")
    else:
        # ルールベースの回答生成
        answer = generate_intelligent_answer(query, search_hits, context)
        logger.info("Answer generated using rule-based system")

    # スニペットを生成
    best_hit = search_hits[0]
    snippet = make_snippet(best_hit.text, query, max_length=200)

    # 信頼度を判定
    confidence = _determine_confidence(search_hits)

    # ソース情報を整理
    sources = _prepare_sources(search_hits[:3])

    return SearchWithLLMResult(
        query=query,
        answer=answer,
        search_hits=search_hits,
        snippet=snippet,
        confidence=confidence,
        sources=sources,
        llm_used=llm_used
    )


def _determine_confidence(hits: List[SearchHit]) -> str:
    """
    検索結果から信頼度を判定

    Args:
        hits: 検索結果リスト

    Returns:
        信頼度（high/medium/low）
    """
    if not hits:
        return "low"

    top_score = hits[0].score

    if top_score >= 100:
        return "high"
    elif top_score >= 60:
        return "medium"
    else:
        return "low"


def _prepare_sources(hits: List[SearchHit]) -> List[Dict[str, Any]]:
    """
    ソース情報を整理

    Args:
        hits: 検索結果（上位数件）

    Returns:
        ソース情報のリスト
    """
    sources = []

    for hit in hits:
        source = {
            "file_name": hit.file_name,
            "page_no": hit.page_no,
            "score": hit.score,
            "section": hit.section,
            "preview": make_snippet(hit.text, "", max_length=100)
        }
        sources.append(source)

    return sources


def format_search_result(result: SearchWithLLMResult) -> str:
    """
    検索結果を整形して表示用テキストを生成

    Args:
        result: 検索結果

    Returns:
        整形されたテキスト
    """
    formatted = []

    # 回答
    formatted.append(f"**回答:**\n{result.answer}\n")

    # スニペット（簡潔な引用）
    if result.snippet:
        formatted.append(f"📌 **関連箇所:**\n{result.snippet}\n")

    # 信頼度
    confidence_emoji = {
        "high": "🟢",
        "medium": "🟡",
        "low": "🔴"
    }
    emoji = confidence_emoji.get(result.confidence, "⚫")
    formatted.append(f"{emoji} **信頼度:** {result.confidence}")

    # LLM使用状況
    if result.llm_used:
        formatted.append("🤖 *AI（LLM）による回答*")
    else:
        formatted.append("📋 *ルールベースによる回答*")

    # 出典
    if result.sources:
        formatted.append("\n📚 **出典:**")
        for i, source in enumerate(result.sources, 1):
            formatted.append(
                f"  {i}. {source['file_name']} - ページ {source['page_no']}"
                + (f" ({source['section']})" if source['section'] else "")
            )

    return "\n".join(formatted)


def search_and_answer(
    query: str,
    context: Optional[str] = None,
    **kwargs
) -> Tuple[str, List[SearchHit]]:
    """
    検索して回答を生成する簡易インターフェース

    Args:
        query: 検索クエリ
        context: 前の会話の文脈
        **kwargs: その他のパラメータ

    Returns:
        (回答テキスト, 検索結果)のタプル
    """
    result = search_with_llm(query, context=context, **kwargs)
    formatted_answer = format_search_result(result)
    return formatted_answer, result.search_hits