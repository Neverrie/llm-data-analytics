import unittest
from unittest.mock import patch

from app.agents.completion import is_usable_finalization, needs_finalization
from app.agents.dataset_agent import run_dataset_agent
from app.agents.prompts import build_system_prompt
from app.agents.requirements import (
    is_analytical_request,
    missing_file_extensions,
    required_file_extensions,
)
from app.llm.models import LlmResponse, LlmToolCall
from app.mcp.models import McpToolResult


class FakeLlmClient:
    instances = []

    def __init__(self):
        self.messages = []
        self.responses = [
            LlmResponse(
                content="",
                tool_calls=[
                    LlmToolCall(
                        id="call-1",
                        name="run_python",
                        arguments={"code": "print('ok')"},
                    )
                ],
            ),
            LlmResponse(content="Анализ завершен: проверка выполнена.", tool_calls=[]),
        ]
        self.__class__.instances.append(self)

    def chat(self, messages, tools=None):
        self.messages.append(messages)
        return self.responses.pop(0)


class FakeToolServer:
    def list_tools(self):
        return [{"name": "run_python", "input_schema": {"type": "object"}}]

    def call_tool(self, call):
        return McpToolResult(
            call_id=call.call_id,
            name=call.name,
            status="success",
            content={
                "sandbox_status": "success",
                "stdout": "ok\n",
                "stderr": "",
                "files": [],
                "elapsed_seconds": 0.01,
                "exit_code": 0,
            },
        )


class AgentArchitectureTests(unittest.TestCase):
    def setUp(self):
        FakeLlmClient.instances.clear()

    def test_system_prompt_is_russian_and_has_no_soft_budget(self):
        prompt = build_system_prompt(dataset_available=True)
        self.assertIn("автономный агент-аналитик", prompt)
        self.assertIn("/input/dataset.csv", prompt)
        self.assertNotIn("4–6", prompt)
        self.assertNotIn("мягк", prompt.lower())

    def test_request_and_file_requirements(self):
        self.assertTrue(is_analytical_request("Проведи анализ датасета"))
        required = required_file_extensions("Сохрани отчет в Markdown и CSV-файл")
        self.assertEqual(required, {".md", ".csv"})
        missing = missing_file_extensions(
            {"report": {"filename": "report.md"}},
            required,
        )
        self.assertEqual(missing, {".csv"})

    def test_finalization_guards(self):
        self.assertTrue(needs_finalization("Сейчас проверю итог"))
        self.assertFalse(is_usable_finalization("..."))
        self.assertTrue(is_usable_finalization("Итоговый анализ завершен."))

    @patch("app.agents.dataset_agent.McpToolServer", FakeToolServer)
    @patch("app.agents.dataset_agent.LlmClient", FakeLlmClient)
    def test_agent_preserves_tool_call_history(self):
        result = run_dataset_agent(
            chat_id="test",
            user_message="Проведи анализ",
            dataset_path="/datasets/test.csv",
        )

        self.assertEqual(result.status, "success")
        self.assertIn("Анализ завершен", result.final_answer)
        second_request = FakeLlmClient.instances[0].messages[1]
        self.assertEqual(
            sum(message.get("role") == "system" for message in second_request),
            1,
        )
        assistant_message = next(
            message
            for message in second_request
            if message.get("role") == "assistant"
        )
        self.assertEqual(assistant_message["tool_calls"][0]["function"]["name"], "run_python")


if __name__ == "__main__":
    unittest.main()
