import socket
import json
import os
import tempfile
from pathlib import Path

import httpx
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.tools import Tool
from streamlit.testing.v1 import AppTest
import unittest
from unittest.mock import patch

with patch('dotenv.load_dotenv', return_value=False):
    from core.config import Config
    from core import model_factory
    from core.rag_pipeline import RAGPipeline
    import app


SETTINGS = {
    'LLM_PROVIDER': 'openai',
    'LLM_MODEL': 'test-chat',
    'LLM_API_KEY': 'synthetic-chat-key',
    'LLM_BASE_URL': '',
    'EMBEDDING_PROVIDER': 'openai',
    'EMBEDDING_MODEL': 'test-embedding',
    'EMBEDDING_API_KEY': 'synthetic-embedding-key',
    'EMBEDDING_BASE_URL': '',
}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        for name, value in SETTINGS.items():
            setting = patch.object(Config, name, value, create=True)
            setting.start()
            self.addCleanup(setting.stop)

    def test_selected_openai_settings_need_no_azure_values(self):
        self.assertEqual(Config.validate_required_settings(), {})

    def test_claude_embeddings_are_rejected(self):
        Config.EMBEDDING_PROVIDER = 'claude'
        self.assertIn('EMBEDDING_PROVIDER', Config.validate_required_settings())

    def test_compatible_endpoint_is_required(self):
        Config.LLM_PROVIDER = 'openai_compatible'
        self.assertIn('LLM_BASE_URL', Config.validate_required_settings())

    def test_factory_returns_regular_openai_clients(self):
        factory = model_factory.ModelFactory()
        self.assertEqual(factory.get_chat_model().model_name, 'test-chat')
        self.assertEqual(factory.get_embedding_model().model, 'test-embedding')

    def test_provider_validation_rejects_missing_values_and_invalid_urls(self):
        for name, value in (("LLM_PROVIDER", "unknown"), ("EMBEDDING_PROVIDER", "claude"),
                            ("LLM_MODEL", ""), ("LLM_API_KEY", ""),
                            ("EMBEDDING_MODEL", ""), ("EMBEDDING_API_KEY", ""),
                            ("LLM_BASE_URL", "file:///tmp/model"),
                            ("EMBEDDING_BASE_URL", "https://user:synthetic-secret@example.test/v1")):
            with self.subTest(name=name, value=value), patch.object(Config, name, value):
                errors = Config.validate_required_settings()
                self.assertIn(name, errors)
                self.assertNotIn("synthetic-secret", str(errors))
                with self.assertRaises(ValueError):
                    model_factory.ModelFactory()

    def test_factory_cache_and_independent_credentials_ignore_ambient_sdk_defaults(self):
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://unwanted.example.test/v1",
                                    "OPENAI_API_KEY": "ambient-synthetic-key"}):
            factory = model_factory.ModelFactory()
            chat = factory.get_chat_model()
            embedding = factory.get_embedding_model()
            self.assertEqual(str(chat.root_client.base_url), "https://api.openai.com/v1/")
            self.assertEqual(str(embedding.client._client.base_url), "https://api.openai.com/v1/")
            self.assertEqual(chat.openai_api_key.get_secret_value(), SETTINGS["LLM_API_KEY"])
            self.assertEqual(embedding.openai_api_key.get_secret_value(), SETTINGS["EMBEDDING_API_KEY"])
            self.assertIs(chat, factory.get_chat_model())
            self.assertIsNot(chat, factory.get_chat_model(0.5))
            self.assertIs(embedding, factory.get_embedding_model())
            factory.clear_cache()
            self.assertIsNot(chat, factory.get_chat_model())
            self.assertIsNot(embedding, factory.get_embedding_model())

    def test_openai_and_compatible_chat_use_expected_http_endpoint_and_auth(self):
        for provider, endpoint in (("openai", "https://api.openai.com/v1"),
                                   ("openai_compatible", "https://chat.example.test/v1")):
            with self.subTest(provider=provider), patch.object(Config, "LLM_PROVIDER", provider), \
                 patch.object(Config, "LLM_BASE_URL", "" if provider == "openai" else endpoint):
                model = model_factory.ModelFactory().get_chat_model()
                requests = []
                def respond(request):
                    requests.append(request)
                    return httpx.Response(200, json={
                        "id": "chatcmpl-fixture", "object": "chat.completion", "created": 0,
                        "model": "test-chat", "choices": [{"index": 0, "message": {
                            "role": "assistant", "content": "fixture analysis"}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    })
                with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                    model.root_client._client = client
                    self.assertEqual(model.invoke("question").text(), "fixture analysis")
                self.assertEqual(str(requests[0].url), endpoint + "/chat/completions")
                self.assertEqual(requests[0].headers["authorization"], "Bearer " + SETTINGS["LLM_API_KEY"])
                self.assertEqual(json.loads(requests[0].content)["model"], "test-chat")

    def test_claude_tool_call_uses_native_messages_api(self):
        Config.LLM_PROVIDER = "claude"
        Config.LLM_MODEL = "test-claude"
        model = model_factory.ModelFactory().get_chat_model()
        self.assertEqual(model.anthropic_api_key.get_secret_value(), SETTINGS["LLM_API_KEY"])
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={
                "id": "msg_fixture", "type": "message", "role": "assistant", "model": "test-claude",
                "content": [{"type": "tool_use", "id": "toolu_fixture", "name": "lookup",
                             "input": {"__arg1": "policy"}}],
                "stop_reason": "tool_use", "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            })
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            model._client._client = client
            result = model.bind_tools([Tool(name="lookup", description="Find evidence", func=lambda query: query)]).invoke("question")
        self.assertEqual(str(requests[0].url), "https://api.anthropic.com/v1/messages")
        self.assertEqual(requests[0].headers["x-api-key"], SETTINGS["LLM_API_KEY"])
        payload = json.loads(requests[0].content)
        self.assertEqual(payload["model"], "test-claude")
        self.assertEqual(payload["tools"][0]["name"], "lookup")
        self.assertEqual(result.tool_calls[0]["name"], "lookup")

    def test_compatible_embeddings_send_raw_text_with_separate_auth(self):
        Config.LLM_PROVIDER = "claude"
        Config.EMBEDDING_PROVIDER = "openai_compatible"
        Config.EMBEDDING_BASE_URL = "https://embedding.example.test/v1"
        embedding = model_factory.ModelFactory().get_embedding_model()
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(200, json={"object": "list", "model": "test-embedding", "data": [
                {"object": "embedding", "index": 0, "embedding": [0.2, 0.4]}],
                "usage": {"prompt_tokens": 2, "total_tokens": 2}})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            embedding.client._client._client = client
            self.assertEqual(embedding.embed_documents(["rate policy"]), [[0.2, 0.4]])
        self.assertEqual(str(requests[0].url), "https://embedding.example.test/v1/embeddings")
        self.assertEqual(requests[0].headers["authorization"], "Bearer " + SETTINGS["EMBEDDING_API_KEY"])
        self.assertEqual(json.loads(requests[0].content)["input"], ["rate policy"])
        self.assertFalse(embedding.check_embedding_ctx_length)

    def test_text_blocks_flow_through_production_graph(self):
        routes = iter(("researcher", "analyst"))
        model = unittest.mock.Mock()
        model.invoke.side_effect = lambda _: AIMessage(content=[{"type": "text", "text": "ROUTE: "},
                                                               {"type": "text", "text": next(routes)}])
        researcher = unittest.mock.Mock()
        researcher.invoke.return_value = {"output": [{"type": "text", "text": "GDP evidence"}]}
        analyst = unittest.mock.Mock()
        analyst.invoke.return_value = {"output": [{"type": "text", "text": "grounded analysis"}]}
        with patch.object(app, "create_agent", side_effect=[researcher, analyst]):
            graph = app.create_graph(model, unittest.mock.Mock())
            result = graph.invoke({"messages": [HumanMessage(content="question")]}, config={"recursion_limit": 23})
        self.assertIn("GDP evidence", analyst.invoke.call_args.args[0]["input"])
        self.assertEqual(result["messages"][-1].text(), "grounded analysis")

    def test_embedding_changes_rebuild_index_even_at_same_dimensions(self):
        from test_documents import write_pdf
        with tempfile.TemporaryDirectory() as folder, patch.object(Config, "DATA_DIR", folder), \
             patch.object(Config, "RAG_USE_COMPRESSION", False):
            write_pdf(Path(folder) / "policy.pdf", ["rate policy"])
            embeddings = DeterministicFakeEmbedding(size=8)
            factory = unittest.mock.Mock()
            factory.get_embedding_model.return_value = embeddings
            first = RAGPipeline(factory)
            first.build_pipeline("same-key")
            marker = Path(folder) / "faiss_index" / "invalidation.txt"
            initial = marker.read_text()
            for key in (SETTINGS["EMBEDDING_API_KEY"], "rotated-synthetic-key"):
                with patch.object(Config, "EMBEDDING_API_KEY", key):
                    cached = RAGPipeline(factory)
                    with patch.object(cached, "_build_new_index", side_effect=AssertionError("must reuse index")):
                        cached.build_pipeline("same-key")
            for name, value in (("EMBEDDING_MODEL", "different-model"),
                                ("EMBEDDING_BASE_URL", "https://different.example.test/v1"),
                                ("EMBEDDING_PROVIDER", "openai_compatible")):
                with self.subTest(name=name), patch.object(Config, name, value):
                    pipeline = RAGPipeline(factory)
                    with patch.object(pipeline, "load_faiss_index", side_effect=AssertionError("old vector space")):
                        pipeline.build_pipeline("same-key")
                    self.assertNotEqual(marker.read_text(), initial)
                    marker.write_text(initial)
            for previous_marker in (b"999999999999.0", b"\xff\xfe"):
                marker.write_bytes(previous_marker)
                pipeline = RAGPipeline(factory)
                with patch.object(pipeline, "load_faiss_index", side_effect=AssertionError("invalid old index")):
                    pipeline.build_pipeline("same-key")
                self.assertEqual(len(marker.read_text()), 64)
            factory.get_chat_model.assert_not_called()

    def test_settings_summary_never_contains_keys_or_url_credentials(self):
        summary = str(Config.get_all_settings())
        self.assertNotIn(SETTINGS["LLM_API_KEY"], summary)
        self.assertNotIn(SETTINGS["EMBEDDING_API_KEY"], summary)
        Config.LLM_BASE_URL = "https://user:synthetic-secret@example.test/v1"
        self.assertNotIn("synthetic-secret", str(Config.get_all_settings()))

    def test_setup_environment_uses_provider_validation(self):
        from utils.helpers import setup_environment
        with patch("utils.helpers.load_dotenv", return_value=False):
            setup_environment()
            Config.LLM_PROVIDER = "invalid"
            with self.assertRaisesRegex(ValueError, "LLM_PROVIDER"):
                setup_environment()

    def test_settings_page_shows_provider_and_key_presence_only(self):
        script = '''
import runpy
page = runpy.run_path("pages/01_⚙️_설정.py")
page["basic_settings_interface"]()
'''
        result = AppTest.from_string(script).run(timeout=20)
        self.assertEqual(list(result.exception), [])
        rendered = "\n".join(item.value for item in result.text)
        self.assertIn("llm_api_key_set: True", rendered)
        self.assertIn("embedding_api_key_set: True", rendered)
        self.assertNotIn(SETTINGS["LLM_API_KEY"], rendered)
        self.assertNotIn(SETTINGS["EMBEDDING_API_KEY"], rendered)


if __name__ == '__main__':
    unittest.main()
