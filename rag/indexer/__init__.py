"""예제 코드 Vector DB 인덱싱 파이프라인.

Agentic AI 예제 코드를 함수·클래스 경계로 청킹·임베딩하여 Chroma Vector DB로 적재함.
"""

__all__ = ["config", "collector", "chunker", "preprocess", "embedder", "store", "pipeline"]
