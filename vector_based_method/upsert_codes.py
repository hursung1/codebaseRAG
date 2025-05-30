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
from vector_based_method.genos_preprocessor import DocumentProcessor

def upsert_to_weaviate(
    collection: weaviate.collections.Collection,
    file_path: str
    ):
    # Use genos preprocessor
    processor = DocumentProcessor()

    try:
        vectors = processor(
            request=None, 
            file_path=file_path, 
            kwargs={"chunk_size":1000000,"chunk_overlap":0})

        for i in range(0, len(vectors), 100):
            start_idx = i
            if i + 100 < len(vectors):
                end_idx = i + 100
            else:
                end_idx = -1
            collection.data.insert_many(vectors[start_idx: end_idx])
    except Exception as e:
        raise Exception(f"Error: {e}")

    return


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
