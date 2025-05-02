import os
import json
import utils
import shutil
import requests
import tempfile
import weaviate
import subprocess

from langchain_core.documents import Document
from concurrent.futures import ThreadPoolExecutor, as_completed

def main():
    chunker = utils.CodeChunker(db_index="codes", reload_db=True)
    
    # 먼저 zip파일 내 모든 파일을 읽어 langchain Document 객체화
    temp_dir = tempfile.mkdtemp()
    try:
        subprocess.run(["unzip", "-q", "code_snippets/Flowise-main.zip", "-d", temp_dir])
    except Exception as e:
        shutil.rmtree(temp_dir)
        raise ValueError(f"Cannot unzip file: {e}")

    try:
        file_paths = [
            os.path.join(root, file)
            for root, _, files in os.walk(temp_dir)
            for file in files
        ]

        all_docs = []

        # 파일 읽기 병렬 처리
        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            futures = {
                executor.submit(utils.load_file, file_path): file_path for file_path in file_paths
            }

            for fut in as_completed(futures):
                docs = fut.result()
                if docs: 
                    all_docs.extend(docs)

    except Exception as e:
        raise Exception(f"Error: {e}")

    finally:
        shutil.rmtree(temp_dir)

    chunker.split_documents(all_docs)
