from pymilvus import MilvusClient

from myharness.vector.splitter import DocumentSpliter




class VectorStoreService:
    def __init__(
            self,
            chunk_size: int = 500,
            overlap: int = 100,
            separators: list[str] | None = None,
            collection_name: str | None = None
    ) -> None:
        self.collection_name = collection_name or "store"
        self.splitter = DocumentSpliter(
            chunk_size=chunk_size,
            overlap=overlap,
            separators=separators,
        )
        self._client: MilvusClient | None = None

    def _get_md5_hex(self) -> str:
        """创建文件的 md5 值"""
        pass

    def _check_md5_hex(self):
        """判断 file_path 是否已入库:库中是否已有与该文件 md5 相同的块。"""
        pass

    def _save_md5_hex(self):
        """文件内md5作为 file_md5 字段随向量块一起持久化在 Milvus"""
        pass

    def _del_md5_hex(self):
        """删除库中文件的 md5 值"""
        pass

    def load_document(self):
        """加载文件到向量库"""
        pass

    def list_documents(self):
        """列出向量库中的所有文档名和它所对应的文档格式、文档大小、分片数量、存储路径"""
        pass

    def del_document(self):
        """删除向量库中的文档和该文档所对应的 md5 值"""
        pass

    def base_retrieve(self, top_k: int = 20):
        pass

    def rerank_retrieve(self, top_k: int = 20, rerank_n: int = 5):
        pass