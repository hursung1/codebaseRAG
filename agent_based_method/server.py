import os 
import mcp
import json
import utils
import httpx
import tempfile
import subprocess

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("file_search")

# functions
async def call_llm(
        model: str = "llama4", 
        prompt: str = "", 
        user_input: str = "",
        tool: list = []) -> dict:
    """
    Call LLM served on GENOS
    """
    token = "f6cc89a65ceb4463b3b289bde30bbf8e"
    url = "https://genos.genon.ai:3443/api/gateway/rep/serving/268"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ],
        "temperature": 0,
        "tool": tool
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url=f"{url}/v1/chat/completions", headers=headers, json=data)
            print(response.text)
            response = response.json()["choices"][0]["message"]
        
        except Exception as e:
            print(f"Error: {str(e)}")
            response = None

    return response


async def get_filetree() -> dict:
    codebase_path = "/Users/seonghwan/projects/codebaseRAG/code_snippets/task_vectors-main"

    if codebase_path.endswith("zip"):
        temp_dir = tempfile.mkdtemp()
        # subprocess.call()
        subprocess.run(
            ["unzip", "-q", codebase_path, "-d", temp_dir],
            check=True,  # 실패 시 CalledProcessError 발생
        )
        codebase_path = temp_dir

    filetree = {} # key: file_path, value: is_unseen
    for path, dirs, files in os.walk(codebase_path):
        for file in files:
            ext = file.split(".")[-1]
            if not f".{ext}" in utils.language_map.keys(): continue
            filetree[f"{path}/{file}"] = True
    
    return filetree


# tools
@mcp.tool()
async def get_files(user_query: str) -> list:
    """
    get appropriate files from file tree with LLM
    """

    filetree = await get_filetree()

    unseen_files = []
    for file, is_unseen in filetree.items():
        if is_unseen:
            unseen_files.append(file)

    prompt = """### 할 일
- 사용자 질의와 파일 목록을 보고, 어떤 파일에서 사용자 질의를 만족할 수 있는 내용이 있을지 파일 경로 및 이름을 통해 유추하고 판단한다.

### 유의사항
- 사용자 질의 의도를 만족할 수 있는 파일의 경로 최대 5가지 만을, python list 형식으로 return 한다.
- 다른 부연설명이나 추가적인 설명은 절대로 return하지 않는다.
- "파일 목록"에 없는 내용을 절대로 return하지 않는다.
"""
    user_input = f"""- 사용자 질의: {user_query}\n- 파일 목록: {unseen_files}"""

    llm_out = await call_llm(prompt=prompt, user_input=user_input)
    llm_out = llm_out["content"].strip()
    if "```" in llm_out:
        llm_out = llm_out.strip("```").strip("python")

    selected_files = json.loads(llm_out.replace("'","\""))

    for file in selected_files:
        filetree[file] = False
        
    return selected_files


if __name__ == "__main__":
    mcp.run(transport='stdio')