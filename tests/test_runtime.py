import tempfile
import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.embeddings import DeterministicFakeEmbedding
from streamlit.testing.v1 import AppTest

with patch("dotenv.load_dotenv", return_value=False):
    import app
    from core.rag_pipeline import RAGPipeline


class RuntimeTests(unittest.TestCase):
    def test_rag_shared_loader_keeps_citation_metadata(self):
        from pathlib import Path
        from test_documents import write_pdf

        with tempfile.TemporaryDirectory() as folder, \
             patch.object(app.Config, "DATA_DIR", folder), \
             patch.object(app.Config, "RAG_USE_COMPRESSION", False):
            write_pdf(Path(folder) / "policy.pdf", ["rate policy"])
            factory = Mock()
            factory.get_embedding_model.return_value = DeterministicFakeEmbedding(size=16)
            retriever = RAGPipeline(factory).build_pipeline("pdf")
            result = retriever.invoke("rate policy")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].metadata["source_filename"], "policy.pdf")
            self.assertEqual(result[0].metadata["page_number"], 1)
            self.assertIn("rate policy", result[0].page_content)

    def test_compiled_graph_carries_budget_and_resets_between_requests(self):
        model = Mock()
        model.invoke.side_effect = lambda _: AIMessage(content="ROUTE: researcher")
        worker = Mock()
        worker.invoke.return_value = {"output": "stored research"}
        with patch.object(app, "create_agent", return_value=worker), \
             patch.object(app.Config, "MAX_ITERATIONS", 2):
            graph = app.create_graph(model, Mock())
            with patch("time.monotonic", return_value=0), patch("time.time", return_value=0):
                result = graph.invoke({"messages": [HumanMessage(content="old history") for _ in range(13)]},
                                      config={"recursion_limit": 7})
            self.assertEqual(result["messages"][-1].content, "ROUTE: END")
            self.assertEqual(worker.invoke.call_count, 2)
            with patch("time.monotonic", return_value=1000), patch("time.time", return_value=1000):
                result = graph.invoke({"messages": [HumanMessage(content="new request")]},
                                      config={"recursion_limit": 7})
            self.assertEqual(result["messages"][-1].content, "ROUTE: END")
            self.assertEqual(worker.invoke.call_count, 4)
            self.assertEqual(model.invoke.call_count, 4)

    def test_analyst_receives_research_and_conversation(self):
        agent = Mock()
        agent.invoke.return_value = {"output": "analysis"}
        app.agent_node({"messages": [
            HumanMessage(content="previous question"),
            AIMessage(content="previous answer"),
            HumanMessage(content="current question"),
            AIMessage(content="GDP grew 2.1%", name="researcher"),
            AIMessage(content="ROUTE: analyst"),
        ]}, agent, "analyst")
        received = agent.invoke.call_args.args[0]["input"]
        for text in ("previous question", "previous answer", "current question", "GDP grew 2.1%"):
            self.assertIn(text, received)
        self.assertNotIn("ROUTE:", received)

    def test_reused_supervisor_starts_a_new_request(self):
        model = Mock()
        model.invoke.return_value = AIMessage(content="ROUTE: researcher")
        supervisor = app.create_supervisor(model, ["researcher", "analyst"])
        with patch("time.time", return_value=0), patch("time.monotonic", return_value=0):
            supervisor({"messages": [HumanMessage(content="first question")]})
        with patch("time.time", return_value=1000), patch("time.monotonic", return_value=1000):
            result = supervisor({"messages": [HumanMessage(content="new question")]})
        last = result["messages"][-1]
        self.assertEqual(last["content"] if isinstance(last, dict) else last.content, "ROUTE: researcher")
        self.assertEqual(model.invoke.call_count, 2)

    def test_long_history_does_not_exhaust_request_budget(self):
        model = Mock()
        model.invoke.return_value = AIMessage(content="ROUTE: researcher")
        supervisor = app.create_supervisor(model, ["researcher", "analyst"])
        result = supervisor({"messages": [HumanMessage(content="history")] * 13})
        last = result["messages"][-1]
        self.assertEqual(last["content"] if isinstance(last, dict) else last.content, "ROUTE: researcher")

    def test_current_request_can_time_out(self):
        model = Mock()
        supervisor = app.create_supervisor(model, ["researcher", "analyst"])
        with patch("time.monotonic", return_value=1000):
            result = supervisor({"messages": [HumanMessage(content="question")],
                                 "started_at": 0, "iterations": 1})
        last = result["messages"][-1]
        self.assertEqual(last["content"] if isinstance(last, dict) else last.content, "ROUTE: END")
        model.invoke.assert_not_called()

    def test_empty_rag_does_not_initialize_models_or_load_old_index(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app.Config, "DATA_DIR", folder):
            factory = Mock()
            factory.get_embedding_model.side_effect = AssertionError("must not initialize embeddings")
            pipeline = RAGPipeline(factory)
            with self.assertRaisesRegex(ValueError, "PDF|문서"):
                pipeline.build_pipeline("empty")
            factory.get_embedding_model.assert_not_called()

    def test_worker_only_updates_produce_final_answer_once(self):
        script = '''
from unittest.mock import patch
from langchain_core.messages import AIMessage
import streamlit as st
import app

class Graph:
    def stream(self, *args, **kwargs):
        yield {"researcher": {"messages": [AIMessage(content="stored evidence", name="researcher")]}}
        yield {"analyst": {"messages": [AIMessage(content="final analysis", name="analyst")]}}
        yield {"chart_processor": {"messages": []}}

app.StateManager.initialize_session_state()
app.StateManager.set_agent_graph(Graph(), app.Config.APP_GRAPH_VERSION)
with patch.object(app, "setup_environment"), patch.object(app, "ModelFactory"), \\
     patch.object(app, "render_sidebar"), \\
     patch.object(app, "render_chat_interface", return_value="question"):
    app.main_chat_interface()
'''
        result = AppTest.from_string(script).run(timeout=20)
        self.assertEqual(list(result.exception), [])
        self.assertEqual(result.session_state["messages"][-1]["content"], "final analysis")
        self.assertEqual(len(result.success), 1)


if __name__ == "__main__":
    unittest.main()
