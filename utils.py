import os
import re
import ast
import json
import requests

from collections import defaultdict

language_map = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".txt": "text",
}


class Analyzer(ast.NodeVisitor):
    def __init__(self):
        self.stats = {"import": [], "from": [], "class": [], "function": []}

    def visit_ImportFrom(self, node):
        for alias in node:
            self.stats["from"].append(alias.name)
        
    def visit_Import(self, node):
        for alias in node.names:
            self.stats["import"].append(alias.name)
        
    def visit_ClassDef(self, node):
        self.stats["class"].append(node.name)
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        self.stats["function"].append(node.name)
        self.generic_visit(node)
    

def call_llm(
        model: str = "llama4", 
        prompt: str = "", 
        user_input: str = "") -> dict:
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
        
    }
    response = requests.post(url=f"{url}/v1/chat/completions", headers=headers, json=data)
    return response.json()["choices"][0]["message"]


def make_subquery(prompts: dict, user_query: str):
    prompt = prompts["subquery_prompt"]
    user_input = f"### 사용자 질의\n- {user_query}\n"

    llm_out = call_llm(prompt=prompt, user_input=user_input)["content"].strip()
    
    try:
        subqueries = json.loads(llm_out)
        return subqueries
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return None


def select_file(prompts: dict, user_query: str, filetree: dict, show_past_docs: bool):
    unseen_files = []
    seen_file_contents = ""
    tokens = 0
    for file, is_unseen in filetree.items():
        if is_unseen:
            unseen_files.append(file)
            tokens += len(file)

        else:
            with open(file, "r") as f:
                seen_file_contents += f"*Filename\n{file}\n*Content\n{f.read()}\n"

        if tokens >= 400000:
            unseen_files = unseen_files[:-1]
            break

    prompt = prompts["select_file_prompt"]
    user_input = f"""- 사용자 질의: {user_query}\n- 파일 목록: {unseen_files}\n"""

    if show_past_docs:
        prompt += prompts["select_file_prompt_add"]
        user_input += f"- 이전 참조 파일 내용: {seen_file_contents}\n"

    llm_out = call_llm(prompt=prompt, user_input=user_input)["content"].strip()

    codeblock_pttn = r"```([\S]*)([\s\S]*)```"
    codeblock_match = re.search(codeblock_pttn, llm_out)

    if codeblock_match:
        selected_files = json.loads(codeblock_match.group(2).replace("'", "\""))
    else:
        selected_files = json.loads(llm_out.replace("'", "\""))
    
    selected_files_refined = []
    for file in selected_files:
        if file in filetree:
            filetree[file] = False
            selected_files_refined.append(file)
        else:
            print(f"Retrieved but not exists: {file}")

    return selected_files_refined
    print(llm_out)


def create_answer(prompts: dict, user_query: str, selected_files: list, answer_candidates: list, handle_code_indiv: bool):
    """
    Get user's query and file paths(selected_files). 
    LLM traverses files and create candidate answers if content of the file matches or is related to user's query.

    Finally, gather and summarize candidate answers into **final_answer**.
    """

    identify_code_prompt = prompts["identify_code_prompt"]

    for i, file in enumerate(selected_files):
        try:
            with open(file, "r") as f:
                codes = f.read()

        except Exception as e:
            print(f"Error: {str(e)}")
            continue

        if handle_code_indiv:
            query_code_user_input = f"""- 사용자 질의: {user_query}\n- 코드 내용: {codes}"""
            
            codeidf_llm_out = call_llm(prompt=identify_code_prompt, user_input=query_code_user_input)["content"].strip()
            print(f"{i}번째 답변:")
            print(codeidf_llm_out)
            print("#" * 30)
            answer_candidates.append(codeidf_llm_out)
        
        else:
            answer_candidates.append(codes)
        
    # 최종 답변 생성
    final_ans_prompt = prompts["final_ans_prompt"]
    final_ans_user_input = f"""- 사용자 질의: {user_query}\n- 파일 별 답변 생성 내용: {answer_candidates}"""
    final_answer = call_llm(prompt=final_ans_prompt, user_input=final_ans_user_input)["content"]
    
    return answer_candidates, final_answer
    print(final_answer)


def find_pckg(package_name: str, module_names: list, root_dir: str):
    """
    현재 package_name이 dir, module_names가 함수명/클래스명일 때 해당 파일을 추가하지 못하는 문제가 있음
    """
    connected_files = []
    for path, dirs, files in os.walk(root_dir):
        if package_name:
            if package_name in dirs: # if package name exists and is in directory: find module_name in dir
                connected_files.extend([os.path.join(path, package_name, f"{module}.py") for module in module_names if f"{module}.py" in files])
            elif f"{package_name}.py" in files: # if package name is file: add that file to connected_files
                connected_files.append(os.path.join(path, f"{package_name}.py"))

        else: # if not package_name: add all module_names to connected_files
            for module in module_names:
                if f"{module}.py" in files:
                    connected_files.append(os.path.join(path, f"{module}.py"))
    
    return connected_files


def get_linked_files(selected_files: list, filetree: dict, root_dir: str):
    linked_files_dict = defaultdict(list)
    for file_path in selected_files:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                package_name = node.module
                module_names = [name.name for name in node.names]

            elif isinstance(node, ast.Import):
                package_name = None
                module_names = [name.name for name in node.names]

            else: continue
            
            connected_files = find_pckg(package_name=package_name, module_names=module_names, root_dir=root_dir)
            linked_files_dict[file_path].extend(connected_files)
            for file in connected_files:
                filetree[file] = False

    return linked_files_dict
