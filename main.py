import os
import sys
import json
import utils
import argparse
import tempfile
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument("--codebase_path", type=str, default="./code_snippets/trl-main")
parser.add_argument("--handle_code_indiv", type=bool, default=False) # 코드 한 번에 프롬프트에 넣을 지 말지
parser.add_argument("--show_past_docs", type=bool, default=False) # 코드 재검색 시 이전 검색 내용을 함께 줄지

if __name__ == "__main__":
    args = parser.parse_args()
    codebase_path = args.codebase_path
    handle_code_indiv = args.handle_code_indiv
    show_past_docs = args.show_past_docs
    
    with open("config.json", "r") as f:
        config = json.load(f)

    user_query = config["query"]
    exp_options = config["exp_options"]
    prompts = config["prompts"]

    final_answer = "pass" # temporaral initialization
    max_count = 5
    count = 0

    if codebase_path.endswith("zip"):
        temp_dir = tempfile.mkdtemp()
        subprocess.run(
            ["unzip", "-q", codebase_path, "-d", temp_dir],
            check=True,  # 실패 시 CalledProcessError 발생
        )
        print(f"Unzipped: {codebase_path}")
        codebase_path = temp_dir

    filetree = {} # key: file_path, value: is_unseen
    for path, dirs, files in os.walk(codebase_path):
        for file in files:
            ext = file.split(".")[-1]
            if not f".{ext}" in utils.language_map.keys(): continue # Only handle when the file is supported language 
            filetree[f"{path}/{file}"] = True
    print("Retrieving filetree completed")

    answer_candidates = []

    while final_answer == "pass" and count < max_count:
        # First, input them into LLM to select appropriate ones
        selected_files = utils.select_file(prompts=prompts, user_query=user_query, filetree=filetree, show_past_docs=show_past_docs)

        # Then, input selected files' paths and user's query to LLM to get final answer
        answer_candidates, final_answer = utils.create_answer(prompts=prompts, user_query=user_query, selected_files=selected_files, answer_candidates=answer_candidates, handle_code_indiv=handle_code_indiv)

        # This is for loop limitation
        count += 1

    print(final_answer)
    print("#"*30)

    with open("log_file.md", "a+") as f:
        f.write(f"# Query\n{user_query}\n\n")
        f.write(f"## Answer\n{final_answer}\n\n")
        f.write(f"### Args: \n- codebase_path: {codebase_path}\n- handle_code_indiv: {handle_code_indiv}\n- show_past_docs: {show_past_docs}\n\n")
