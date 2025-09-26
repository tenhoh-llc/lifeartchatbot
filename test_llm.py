"""
LLM統合検索のテストコード
"""
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from pdf.search import SearchHit
from pdf.llm_answer import LLMAnswerGenerator, LLMConfig, generate_llm_answer
from pdf.search_with_llm import search_with_llm, format_search_result, SearchWithLLMResult


def test_llm_answer_generator_without_api():
    """APIキーなしでLLM生成器をテスト（フォールバック動作）"""
    print("\n=== Test LLM Answer Generator Without API ===")

    # モックの検索結果を作成
    mock_hits = [
        SearchHit(
            file_name="就業規則.pdf",
            page_no=10,
            score=95.0,
            text="育児休業は、原則として子が1歳に達するまでの間、取得することができます。ただし、保育園に入れない等の事情がある場合は、最長2歳まで延長可能です。",
            section="第5章 育児・介護休業",
            file_path="./data/pdfs/就業規則.pdf"
        ),
        SearchHit(
            file_name="育児介護休業規程.pdf",
            page_no=3,
            score=80.0,
            text="育児休業の申請は、休業開始予定日の1か月前までに、所定の申請書を人事部に提出してください。",
            section="第2条 申請手続き",
            file_path="./data/pdfs/育児介護休業規程.pdf"
        )
    ]

    # LLMが無効な設定でテスト
    with patch.dict(os.environ, {"LLM_PROVIDER": "none"}):
        # 簡易的な回答を生成（LLMなし）
        answer = generate_llm_answer(
            query="育児休業はいつまで取れますか？",
            search_results=mock_hits,
            context=None,
            use_llm=False
        )

        print(f"Query: 育児休業はいつまで取れますか？")
        print(f"Answer (without LLM):\n{answer}\n")

        assert "育児休業" in answer or "1歳" in answer
        print("✓ Fallback answer generation works")


def test_llm_answer_generator_with_mock_api():
    """モックAPIを使用してLLM生成器をテスト"""
    print("\n=== Test LLM Answer Generator With Mock API ===")

    # モックの検索結果
    mock_hits = [
        SearchHit(
            file_name="就業規則.pdf",
            page_no=10,
            score=95.0,
            text="有給休暇は入社6か月後から10日付与されます。",
            section="第4章 休暇",
            file_path="./data/pdfs/就業規則.pdf"
        )
    ]

    # OpenAIクライアントをモック
    with patch('pdf.llm_answer.OpenAI') as MockOpenAI:
        # モックレスポンスを設定
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="有給休暇は入社6か月後から10日付与されます。その後、勤続年数に応じて日数が増加します。\n\n出典: 就業規則.pdf - ページ10"))
        ]
        mock_client.chat.completions.create.return_value = mock_response
        MockOpenAI.return_value = mock_client

        # LLM設定
        config = LLMConfig(
            provider="openai",
            api_key="mock-api-key",
            model="gpt-4o-mini",
            temperature=0.3
        )

        # 生成器を初期化
        generator = LLMAnswerGenerator(config)

        # 回答を生成
        answer = generator.generate_answer(
            query="有給休暇はいつから取れますか？",
            search_results=mock_hits,
            context=None
        )

        print(f"Query: 有給休暇はいつから取れますか？")
        print(f"Answer (with mock LLM):\n{answer}\n")

        assert "入社6か月" in answer or "10日" in answer
        print("✓ LLM answer generation with mock API works")


def test_search_with_llm_integration():
    """検索とLLM統合のテスト"""
    print("\n=== Test Search With LLM Integration ===")

    # モック検索結果
    mock_hits = [
        SearchHit(
            file_name="給与規程.pdf",
            page_no=5,
            score=100.0,
            text="給与の支払日は毎月25日とする。ただし、25日が休日の場合は前営業日に支払う。",
            section="第3条 支払日",
            file_path="./data/pdfs/給与規程.pdf"
        )
    ]

    # search関数をモック
    with patch('pdf.search_with_llm.search') as mock_search:
        mock_search.return_value = mock_hits

        # LLMを無効にしてテスト（環境変数で制御）
        with patch.dict(os.environ, {"LLM_PROVIDER": "none"}):
            result = search_with_llm(
                query="給与の支払日はいつですか？",
                top_k=5,
                use_llm=False
            )

            print(f"Query: {result.query}")
            print(f"Answer:\n{result.answer}\n")
            print(f"Confidence: {result.confidence}")
            print(f"LLM Used: {result.llm_used}")
            print(f"Sources: {len(result.sources)} sources found")

            assert isinstance(result, SearchWithLLMResult)
            assert result.query == "給与の支払日はいつですか？"
            assert result.confidence == "high"  # スコア100なのでhigh
            assert not result.llm_used  # LLMは使用されていない
            assert len(result.sources) == 1

            print("✓ Search with LLM integration works")


def test_format_search_result():
    """検索結果のフォーマットテスト"""
    print("\n=== Test Format Search Result ===")

    # テスト用の結果を作成
    test_result = SearchWithLLMResult(
        query="テストクエリ",
        answer="これはテスト回答です。",
        search_hits=[
            SearchHit(
                file_name="test.pdf",
                page_no=1,
                score=90.0,
                text="テストテキスト",
                section="テストセクション",
                file_path="./test.pdf"
            )
        ],
        snippet="テストスニペット",
        confidence="high",
        sources=[
            {
                "file_name": "test.pdf",
                "page_no": 1,
                "score": 90.0,
                "section": "テストセクション",
                "preview": "テストプレビュー"
            }
        ],
        llm_used=True
    )

    # フォーマット
    formatted = format_search_result(test_result)

    print(f"Formatted result:\n{formatted}\n")

    assert "**回答:**" in formatted
    assert "これはテスト回答です" in formatted
    assert "🟢" in formatted  # high confidence
    assert "🤖" in formatted  # LLM used
    assert "test.pdf" in formatted

    print("✓ Result formatting works")


def test_llm_error_handling():
    """LLMエラー処理のテスト"""
    print("\n=== Test LLM Error Handling ===")

    mock_hits = [
        SearchHit(
            file_name="test.pdf",
            page_no=1,
            score=90.0,
            text="テストテキスト",
            section="テストセクション",
            file_path="./test.pdf"
        )
    ]

    # OpenAIクライアントをモックしてエラーを発生させる
    with patch('pdf.llm_answer.OpenAI') as MockOpenAI:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        MockOpenAI.return_value = mock_client

        config = LLMConfig(
            provider="openai",
            api_key="mock-api-key"
        )

        generator = LLMAnswerGenerator(config)

        # エラーが発生してもフォールバックで回答が生成されることを確認
        answer = generator.generate_answer(
            query="テストクエリ",
            search_results=mock_hits,
            context=None
        )

        print(f"Answer after error (fallback):\n{answer}\n")

        assert answer  # 何か回答が返される
        assert "test.pdf" in answer or "テスト" in answer

        print("✓ Error handling with fallback works")


def main():
    """全テストを実行"""
    print("\n" + "=" * 60)
    print("LLM Integration Tests")
    print("=" * 60)

    try:
        test_llm_answer_generator_without_api()
        test_llm_answer_generator_with_mock_api()
        test_search_with_llm_integration()
        test_format_search_result()
        test_llm_error_handling()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()