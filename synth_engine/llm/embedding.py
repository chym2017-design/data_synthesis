"""
Embedding 服务

提供文本 embedding 向量和余弦相似度计算。
"""

from typing import List, Optional

import numpy as np


def get_embedding(
    text: str,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str = "将银行客服对话文本转换为语义向量表示，用于计算文本之间的语义相似度",
    timeout: int = 30,
) -> Optional[np.ndarray]:
    """获取文本的 embedding 向量"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        completion = client.embeddings.create(
            model=model,
            input=f"Instruct: {system_prompt}\nQuery: {text}",
        )
        return np.array(completion.data[0].embedding)
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None


def compute_cosine_similarity_matrix(embeddings: List[np.ndarray]) -> np.ndarray:
    """计算余弦相似度矩阵"""
    valid = []
    dim = None
    for e in embeddings:
        if e is not None:
            valid.append(e)
            if dim is None:
                dim = len(e)
        else:
            valid.append(np.zeros(dim or 768))

    matrix = np.stack(valid)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = matrix / norms
    return np.dot(normalized, normalized.T)


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """计算两个向量的余弦相似度"""
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))
