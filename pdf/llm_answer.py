"""
LLM（OpenAI）を使用した回答生成モジュール
検索結果を基にLLMで自然な回答を生成
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import os
from loguru import logger
import openai
from openai import OpenAI
from core.config import AppConfig


@dataclass
class LLMConfig:
    """LLM設定"""
    provider: str
    api_key: str
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1000


class LLMAnswerGenerator:
    """
    LLMを使用して回答を生成するクラス
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初期化

        Args:
            config: LLM設定
        """
        if config is None:
            # 環境変数から設定を読み込み
            app_config = AppConfig.load()
            if app_config.llm_provider == "none":
                self.enabled = False
                self.client = None
                logger.warning("LLM is disabled (provider=none)")
                return

            if app_config.llm_provider != "openai":
                raise ValueError(f"Currently only OpenAI is supported, got: {app_config.llm_provider}")

            config = LLMConfig(
                provider=app_config.llm_provider,
                api_key=app_config.llm_api_key or ""
            )

        self.config = config
        self.enabled = True

        # OpenAIクライアントを初期化
        if config.provider == "openai":
            self.client = OpenAI(api_key=config.api_key)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

        logger.info(f"LLM Answer Generator initialized with {config.provider}")

    def generate_answer(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        context: Optional[str] = None
    ) -> str:
        """
        LLMを使用して回答を生成

        Args:
            query: ユーザーのクエリ
            search_results: 検索結果のリスト
            context: 前の会話の文脈

        Returns:
            生成された回答
        """
        if not self.enabled:
            # LLMが無効の場合は簡易的な回答を返す
            return self._generate_simple_answer(query, search_results)

        if not search_results:
            return "申し訳ございません。該当する情報が見つかりませんでした。より具体的な質問をいただければ、お答えできるかもしれません。"

        try:
            # 検索結果から関連情報を抽出
            context_info = self._prepare_context(search_results)

            # プロンプトを構築
            prompt = self._build_prompt(query, context_info, context)

            # OpenAI APIを呼び出し
            response = self._call_llm(prompt)

            return response

        except Exception as e:
            logger.error(f"LLM error: {e}")
            # エラー時はフォールバック
            return self._generate_simple_answer(query, search_results)

    def _prepare_context(self, search_results: List[Dict[str, Any]]) -> str:
        """
        検索結果から文脈情報を準備

        Args:
            search_results: 検索結果

        Returns:
            文脈情報の文字列
        """
        context_parts = []

        for i, result in enumerate(search_results[:3], 1):  # 上位3件を使用
            # SearchHitオブジェクトの属性を取得
            text = result.text if hasattr(result, 'text') else result.get('text', '')
            file_name = result.file_name if hasattr(result, 'file_name') else result.get('file_name', '')
            page_no = result.page_no if hasattr(result, 'page_no') else result.get('page_no', 0)
            section = result.section if hasattr(result, 'section') else result.get('section', '')

            # 文脈を構築
            context_parts.append(f"【参照{i}】")
            context_parts.append(f"文書: {file_name} - ページ {page_no}")
            if section:
                context_parts.append(f"セクション: {section}")
            context_parts.append(f"内容: {text[:500]}...")  # 最初の500文字
            context_parts.append("")

        return "\n".join(context_parts)

    def _build_prompt(
        self,
        query: str,
        context_info: str,
        previous_context: Optional[str] = None
    ) -> str:
        """
        LLM用のプロンプトを構築

        Args:
            query: ユーザーのクエリ
            context_info: 検索結果の文脈情報
            previous_context: 前の会話の文脈

        Returns:
            プロンプト文字列
        """
        system_prompt = """あなたは社内規程に詳しいアシスタントです。
以下のルールに従って回答してください：

1. 提供された参照情報に基づいて正確に回答する
2. 規程の内容を正確に伝え、解釈や推測は避ける
3. 該当する条件や例外事項があれば明確に示す
4. 回答は簡潔で分かりやすく、箇条書きを活用する
5. 参照した規程名とページ番号を明記する
6. 不明な点は「規程に記載がない」と正直に伝える"""

        user_prompt = f"""【質問】
{query}

【参照情報】
{context_info}

【回答要件】
- 参照情報に基づいて正確に回答してください
- 該当する条件や制限事項があれば明記してください
- 参照元（文書名・ページ）を含めてください"""

        if previous_context:
            user_prompt = f"【前の文脈】\n{previous_context}\n\n" + user_prompt

        return system_prompt, user_prompt

    def _call_llm(self, prompt: tuple) -> str:
        """
        LLM APIを呼び出して回答を生成

        Args:
            prompt: (system_prompt, user_prompt)のタプル

        Returns:
            生成された回答
        """
        system_prompt, user_prompt = prompt

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _generate_simple_answer(
        self,
        query: str,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """
        LLMを使わない簡易的な回答を生成（フォールバック用）

        Args:
            query: クエリ
            search_results: 検索結果

        Returns:
            簡易的な回答
        """
        if not search_results:
            return "該当する情報が見つかりませんでした。"

        # 最も関連性の高い結果を取得
        best_result = search_results[0]

        text = best_result.text if hasattr(best_result, 'text') else best_result.get('text', '')
        file_name = best_result.file_name if hasattr(best_result, 'file_name') else best_result.get('file_name', '')
        page_no = best_result.page_no if hasattr(best_result, 'page_no') else best_result.get('page_no', 0)

        # テキストの最初の200文字を抽出
        summary = text[:200] + "..." if len(text) > 200 else text

        answer = f"📄 **関連情報**\n\n{summary}\n\n"
        answer += f"📚 出典: {file_name} - ページ {page_no}"

        return answer


# グローバルインスタンス（シングルトン）
_llm_generator = None


def get_llm_generator() -> Optional[LLMAnswerGenerator]:
    """LLM回答生成器のインスタンスを取得"""
    global _llm_generator
    if _llm_generator is None:
        try:
            _llm_generator = LLMAnswerGenerator()
        except Exception as e:
            logger.warning(f"Failed to initialize LLM generator: {e}")
            return None
    return _llm_generator


def generate_llm_answer(
    query: str,
    search_results: List[Any],
    context: Optional[str] = None,
    use_llm: bool = True
) -> str:
    """
    LLMを使用して回答を生成（エントリーポイント）

    Args:
        query: ユーザーのクエリ
        search_results: 検索結果のリスト
        context: 前の会話の文脈
        use_llm: LLMを使用するかどうか

    Returns:
        生成された回答
    """
    if not use_llm:
        # LLMを使わない場合は既存の実装を使用
        from pdf.intelligent_answer import generate_intelligent_answer
        return generate_intelligent_answer(query, search_results, context)

    # LLM生成器を取得
    generator = get_llm_generator()

    if generator is None or not generator.enabled:
        # LLMが利用できない場合は既存の実装を使用
        from pdf.intelligent_answer import generate_intelligent_answer
        return generate_intelligent_answer(query, search_results, context)

    # LLMで回答を生成
    return generator.generate_answer(query, search_results, context)