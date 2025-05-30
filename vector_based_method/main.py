"""
main 함수의 역할
1. 사용자로부터 query를 받는다.
2. 받은 query를 이용해 RAG를 실행한다.
3. LLM을 이용하여 검색 품질을 판단한다.
3-1. 만약 검색 품질이 만족스러우면: 해당 검색 결과를 기반으로 답변을 생성 후 제공한다.
3-2. 검색 품질이 만족스럽지 못하면: 적재 안 된 일부 파일을 다시 적재 후 2로 되돌아간다.
"""
import utils
import weaviate

from vector_based_method.upsert_codes import upsert_to_weaviate

if __name__ == "__main__": 
    # connect to weaviate
    collection_name = "local_codebase"
    client = weaviate.connect_to_local()
    client.collections.delete(collection_name)
    collection = client.collections.create(
        name=collection_name,
        vectorizer_config=weaviate.classes.config.Configure.Vectorizer.text2vec_ollama(
            api_endpoint="http://host.docker.internal:11434",
            model="qwen3:latest"
        )
    )

    # First: Get user query and file path
    user_query = input("Query: ")
    file_path = input("File path: ")

    while True: 
        # Second: Upsert a portion of codes to weaviate
        upsert_to_weaviate(collection=collection, file_path=file_path)

        query_vector = utils.vectorize(user_query)

        # Third: RAG
        ret_out = collection.query.near_vector(near_vector=query_vector)

        # Fourth: Evaluate retrieval quality
        prompt = "사용자의 질의문과 검색 결과를 비교하여, 현재의 검색 결과로 충분한 답을 줄 수 있는지 없는지 판단하여야 한다. 무조건 다음 두 가지 선택지 중 하나로만 답해야 한다.\n\n1. \"Yes\": 사용자 질의 의도를 충분히 만족시킬 수 있는 답변을 제공할 수 있는 검색 결과인 경우\n2. \"No\": 사용자 질의 의도를 만족시킬 수 없는 검색 결과인 경우\n\n절대로 다른 표현이나 설명을 덧붙이지 않는다."
        user_input = f"""사용자 질의: {user_query}
    검색 결과: {ret_out}
    """
        llm_answer = utils.call_llm(prompt=prompt, user_input=user_input)["content"]
        if "yes" in llm_answer.lower(): # Good quality: create response
            break
        else: # Bad quality: upsert codes then RAG again
            upsert_to_weaviate(collection=collection, )

    prompt = ""
    user_input = ""
    llm_answer = utils.call_llm(prompt=prompt, user_input=user_input)["content"]
    print(f"{llm_answer}")
    client.close()