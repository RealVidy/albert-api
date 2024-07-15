from typing import List, Optional

from langchain_community.vectorstores import Qdrant
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from fastapi import HTTPException
from qdrant_client.http import models as rest


class BaseRAG:
    """
    Base RAG, basic retrival augmented generation.

    Args:
        embeddings_model (str): OpenAI embeddings model
        collection (List[Optional[str]]): Collection names. Defaults to "user" parameter.
        file_ids (Optional[List[str]], optional): List of file ids for user collections (after upload files). Defaults to None.
        k (int, optional): Top K per collection (max: 6). Defaults to 4.
        prompt_template (Optional[str], optional): Prompt template. Defaults to DEFAULT_PROMPT_TEMPLATE.
    """

    DEFAULT_PROMPT_TEMPLATE = "Réponds à la question suivante en te basant sur les documents ci-dessous : %(prompt)s\n\nDocuments :\n\n%(docs)s"
    MAX_K = 6

    def __init__(self, clients: dict, user: str):
        self.user = user
        self.clients = clients

    async def get_prompt(
        self,
        embeddings_model: str,
        collections: List[Optional[str]],
        file_ids: Optional[List[str]] = None,
        k: Optional[int] = 4,
        prompt_template: Optional[str] = DEFAULT_PROMPT_TEMPLATE,
        **request,
    ) -> str:
        if k > self.MAX_K:
            raise HTTPException(status_code=400, detail=f"K must be less than or equal to {self.MAX_K}")

        embeddings =" HuggingFaceEndpointEmbeddings"(
            model=self.clients["openai"][embeddings_model].base_url,
            huggingfacehub_api_token=self.clients["openai"][embeddings_model].api_key,
        )

        all_collections = [
            collection.name for collection in self.clients["vectors"].get_collections().collections
        ]
        filter = rest.Filter(must=[rest.FieldCondition(key="metadata.file_id", match=rest.MatchAny(any=file_ids))]) if file_ids else None  # fmt: off
        prompt = request["messages"][-1]["content"]

        docs = []
        for collection in collections:
            # check if collections exists
            if collection not in all_collections:
                raise HTTPException(status_code=404, detail=f"Collection {collection} not found")

            vectorstore = Qdrant(
                client=self.clients["vectors"],
                embeddings=embeddings,
                collection_name=collection,
            )
            docs.extend(vectorstore.similarity_search(prompt, k=k, filter=filter))
        
        docs = "\n\n".join([doc.page_content for doc in docs])

        prompt = prompt_template % {"docs": docs, "prompt": prompt}

        return prompt
