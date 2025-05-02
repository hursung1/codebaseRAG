import requests
import weaviate

from pathlib import Path
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

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


class CodeChunker:
    def __init__(self, db_index, split_strategy="length", reload_db=False):
        assert split_strategy in ["length", "language", "hierarchical"] 

        self.client = weaviate.connect_to_local()
        if reload_db:
            self.client.collections.delete(db_index)
            self.collection = self.client.collections.create(db_index)

        else:
            self.collection = self.client.collections.get(db_index)

        self.text_splitter = RecursiveCharacterTextSplitter()
        self.split_strategy = split_strategy

    def split_documents(self, documents: list[Document]):
        """
        Split documents into smaller chunks.
        Split method would be selected by option.
        """
        if self.split_strategy == "length":
            return self.split_length(documents)
        
        elif self.split_strategy == "language":
            return self.split_language(documents)
        
        elif self.split_strategy == "hierarchical":
            return self.split_hierarchical(documents)
        
        self.close_client()

    def split_length(self, documents):
        """
        Default option. Chunk documents with length
        """
        chunks = self.text_splitter.split_documents(documents)
        chunks = [chunk for chunk in chunks if chunk.page_content]

        chunks_for_weaviate = []
        for chunk in chunks:
            chunks_for_weaviate.append(
                weaviate.classes.data.DataObject(
                    properties={
                        "text": chunk.page_content,
                        "source": chunk.metadata.get("source", "unknown"),
                        "language": chunk.metadata.get("language", "unknown"),
                        "file_type": chunk.metadata.get("filetype", "unknown")
                    },
                    vector=vectorize(chunk.page_content)
                ))
            
            if len(chunks_for_weaviate) % 1000 == 0:
                self.collection.data.insert_many(chunks_for_weaviate)
                chunks_for_weaviate = []

        self.collection.data.insert_many(chunks_for_weaviate)

    def split_language(self, documents: list[Document]):
        """
        Split documents by language
        """
        for doc in documents:
            text_splitter = self.text_splitter.from_language(language=doc.metadata["language"])

        

    def split_hierarchical(self, documents):
        """
        Split documents by hierarchical structure
        """

    def upsert_chunks(self, chunks):
        """
        """

    def close_client(self):
        self.client.close()


    def add_description(self, chunks):
        """
        Add description for code chunks
        """

        


def detect_encoding(file_path: str) -> str:
    encodings = ["utf-8", "utf-16", "utf-32", "ascii", "latin-1"]
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                f.read()
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"  # 기본값


def load_file(path):
    encoding = detect_encoding(path)
    filetype = Path(path).suffix.lower()
    with open(path, "r", encoding=encoding) as f:
        document = f.read()

    return [
        Document(
            page_content=document,
            metadata={
                "source": path,
                "language": language_map.get(filetype, "unknown"),
                "filetype": filetype
            }
        )
    ]

def vectorize(input_str: str) -> list[float]:
    """
    Genos에 올라간 embedding 호출하여 vectorize
    """

    emb_url = "https://genos.mnc.ai:3443/api/gateway/rep/serving/10/v1/embeddings"
    emb_key = "d2278640406c48b1b626ae5963fa25a1"
    emb_headers = {
        "Content-Type": "application/json", "Authorization": f"Bearer {emb_key}"
    }
    input_data = {
        "input": [input_str]
    }
    try:
        response = requests.post(url=emb_url, headers=emb_headers, json=input_data)
        return response.json()["data"][0]["embedding"]
    
    except Exception as e:
        print(f"Error in vectorize: {str(e)}")
        return None