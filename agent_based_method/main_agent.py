"""
together ai로 구현한 mcp client
"""
import sys
import json
import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from utils import GenosServedLM

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from together import Together
from dotenv import load_dotenv

# load_dotenv()

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.model = GenosServedLM(model_id=268, model_name="llama4", api_key="f6cc89a65ceb4463b3b289bde30bbf8e")

    async def connect_to_server(self, server_script_path: str):
        """
        MCP 서버에 연결하는 method
        """
        server_params = StdioServerParameters(
            command="python",
            args=[server_script_path],
            env=None
        )

        # 무슨 역할을 할까요?
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # 사용가능한 tool 목록을 생성
        response = await self.session.list_tools()
        tools = response.tools
        print(f"\nConnected to server with tools: {[tool.name for tool in tools]}")

    async def process_query(self, query: str,) -> str:
        """
        LLM과 사용가능한 tool을 이용해 query를 처리
        """
        response = await self.session.list_tools()
        avaliable_tools = [{
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema,
            "required": list(tool.inputSchema.keys()),
            "additionalProperties": False
        } for tool in response.tools]

        # LLM 호출
        response = await self.model(prompt="", user_input=query, tools=avaliable_tools)

        # 응답을 처리한 후 적절한 tool 호출
        final_text = []
        assistant_message_content = []
        res_message = response.choices[0].message

        print(res_message)

        if res_message.role == "system":
            final_text.append(res_message.content)
            assistant_message_content.append(res_message)

        elif res_message.role == "assistant":
            for tool in res_message.tool_calls: # together ai는 list 형식의 "tool_calls"로 호출해야 할 tool들을 return함
                tool_name = tool.function.name
                tool_args = tool.function.arguments

                # Execute tool call
                result = await self.session.call_tool(tool_name, json.loads(tool_args))
                final_text.append(f"[{tool_name} 함수롤 {tool_args} 인자와 함께 호출함]")
                assistant_message_content.append(tool_name) # 일단은 모델이 호출한 함수명을 넣는걸로. openai에서는 res_message 그대로 넣어줌
                messages.append({
                    "role": "assistant",
                    "content": tool_name
                })
                messages.append({
                    "role": "tool",
                    "content": result.content[0].text
                })

                response = self.together.chat.completions.create(
                    model="Qwen/Qwen2.5-72B-Instruct-Turbo",
                    messages=messages,
                    tools=avaliable_tools,
                )

                final_text.append(response.choices[0].message.content)

        return "\n".join(final_text)

    async def chat_loop(self):
        """
        chat loop 실행
        """

        print("MCP 클라이언트를 실행합니다.\n'quit'을 입력하면 종료합니다.")

        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == "quit":
                    break

                response = await self.process_query(query)
                print(f"\n{response}")

            except Exception as e:
                print(f"\nError: {str(e)}")

    async def cleanup(self):
        """
        리소스 정리
        """
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
