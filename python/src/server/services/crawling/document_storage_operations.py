"""
Document Storage Operations

Handles the storage and processing of crawled documents.
Extracted from crawl_orchestration_service.py for better modularity.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from ...config.logfire_config import get_logger, safe_logfire_error, safe_logfire_info
from ..credential_service import credential_service
from ..source_management_service import extract_source_summary, update_source_info
from ..storage.document_storage_service import add_documents_to_supabase
from ..storage.storage_services import DocumentStorageService
from .code_extraction_service import CodeExtractionService

logger = get_logger(__name__)


class DocumentStorageOperations:
    """
    Handles document storage operations for crawled content.
    """

    def __init__(self, supabase_client):
        """
        Initialize document storage operations.

        Args:
            supabase_client: The Supabase client for database operations
        """
        self.supabase_client = supabase_client
        self.doc_storage_service = DocumentStorageService(supabase_client)
        self.code_extraction_service = CodeExtractionService(supabase_client)

    async def process_and_store_documents(
        self,
        crawl_results: list[dict],
        request: dict[str, Any],
        crawl_type: str,
        original_source_id: str,
        progress_callback: Callable | None = None,
        cancellation_check: Callable | None = None,
        source_url: str | None = None,
        source_display_name: str | None = None,
        url_to_page_id: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Process crawled documents and store them in the database.

        Args:
            crawl_results: List of crawled documents
            request: The original crawl request
            crawl_type: Type of crawl performed
            original_source_id: The source ID for all documents
            progress_callback: Optional callback for progress updates
            cancellation_check: Optional function to check for cancellation
            source_url: Optional original URL that was crawled
            source_display_name: Optional human-readable name for the source

        Returns:
            Dict containing storage statistics and document mappings
        """
        # Reuse initialized storage service for chunking
        storage_service = self.doc_storage_service

        source_word_counts = {original_source_id: 0}
        url_to_full_document = {}
        processed_docs = 0
        prepared_documents: list[dict[str, str]] = []
        source_summary_contents: list[str] = []
        source_summary_metadatas: list[dict[str, Any]] = []

        # Prepare documents for storage and source metadata
        for doc_index, doc in enumerate(crawl_results):
            # Check for cancellation during document processing
            if cancellation_check:
                try:
                    cancellation_check()
                except asyncio.CancelledError:
                    if progress_callback:
                        await progress_callback(
                            "cancelled",
                            99,
                            f"Document processing cancelled at document {doc_index + 1}/{len(crawl_results)}"
                        )
                    raise

            doc_url = (doc.get('url') or '').strip()
            markdown_content = (doc.get('markdown') or '').strip()

            # Skip documents with empty or whitespace-only content or missing URLs
            if not markdown_content or not doc_url:
                logger.debug(f"Skipping document {doc_index}: empty {'URL' if not doc_url else 'content'}")
                continue

            # Increment processed document count
            processed_docs += 1

            # Store full document for code extraction context
            url_to_full_document[doc_url] = markdown_content

            prepared_documents.append(
                {
                    "url": doc_url,
                    "markdown": markdown_content,
                    "title": str(doc.get("title", "")),
                    "description": str(doc.get("description", "")),
                }
            )

            source_word_count = len(markdown_content.split())
            source_word_counts[original_source_id] = source_word_counts.get(original_source_id, 0) + source_word_count

            # Keep summary inputs bounded to avoid retaining large intermediate text in memory.
            source_summary_contents.append(markdown_content[:5000])
            source_summary_metadatas.append(
                {
                    "source_id": original_source_id,
                    "word_count": source_word_count,
                }
            )

            # Yield control after processing each document
            if doc_index > 0 and doc_index % 5 == 0:
                await asyncio.sleep(0)

        if not prepared_documents:
            return {
                "chunk_count": 0,
                "chunks_stored": 0,
                "total_word_count": 0,
                "url_to_full_document": {},
                "source_id": original_source_id,
            }

        # Create/update source record FIRST (required for FK constraints on pages and chunks)
        if source_summary_contents and source_summary_metadatas:
            await self._create_source_records(
                source_summary_metadatas,
                source_summary_contents,
                source_word_counts,
                request,
                source_url,
                source_display_name,
            )

        # Store pages AFTER source is created but BEFORE chunks (FK constraint requirement)
        from .page_storage_operations import PageStorageOperations

        page_storage_ops = PageStorageOperations(self.supabase_client)

        # Check if this is an llms-full.txt file
        is_llms_full = crawl_type == "llms-txt" or (
            len(url_to_full_document) == 1
            and next(iter(url_to_full_document.keys())).endswith("llms-full.txt")
        )

        chunk_count = 0
        chunks_stored = 0

        if is_llms_full and url_to_full_document:
            # Handle llms-full.txt with section-based pages
            base_url = next(iter(url_to_full_document.keys()))
            content = url_to_full_document[base_url]

            # Store section pages
            url_to_page_id = await page_storage_ops.store_llms_full_sections(
                base_url,
                content,
                original_source_id,
                request,
                crawl_type="llms_full",
            )

            # Parse sections and re-chunk each section
            from .helpers.llms_full_parser import parse_llms_full_sections

            sections = parse_llms_full_sections(content, base_url)

            all_urls = []
            all_chunk_numbers = []
            all_contents = []
            all_metadatas = []
            url_to_full_document.clear()

            # Chunk each section separately
            for section in sections:
                # Update url_to_full_document with section content
                url_to_full_document[section.url] = section.content
                section_chunks = await storage_service.smart_chunk_text_async(
                    section.content, chunk_size=5000
                )

                for i, chunk in enumerate(section_chunks):
                    all_urls.append(section.url)
                    all_chunk_numbers.append(i)
                    all_contents.append(chunk)

                    word_count = len(chunk.split())
                    metadata = {
                        "url": section.url,
                        "title": section.section_title,
                        "description": "",
                        "source_id": original_source_id,
                        "knowledge_type": request.get("knowledge_type", "documentation"),
                        "page_id": url_to_page_id.get(section.url),
                        "crawl_type": "llms_full",
                        "word_count": word_count,
                        "char_count": len(chunk),
                        "chunk_index": i,
                        "tags": request.get("tags", []),
                    }
                    all_metadatas.append(metadata)

            storage_stats = await add_documents_to_supabase(
                client=self.supabase_client,
                urls=all_urls,
                chunk_numbers=all_chunk_numbers,
                contents=all_contents,
                metadatas=all_metadatas,
                url_to_full_document=url_to_full_document,
                batch_size=25,
                progress_callback=progress_callback,
                enable_parallel_batches=True,
                provider=None,
                cancellation_check=cancellation_check,
                url_to_page_id=url_to_page_id,
            )
            chunk_count = len(all_contents)
            chunks_stored = storage_stats.get("chunks_stored", 0)
        else:
            url_to_page_id = await page_storage_ops.store_pages(
                prepared_documents,
                original_source_id,
                request,
                crawl_type,
            )

            try:
                rag_settings = await credential_service.get_credentials_by_category("rag_strategy")
                raw_flush_size = int(rag_settings.get("DOCUMENT_STORAGE_FLUSH_CHUNKS", "250"))
                flush_chunk_size = max(25, raw_flush_size)
            except Exception as e:
                logger.warning(f"Failed to load DOCUMENT_STORAGE_FLUSH_CHUNKS setting: {e}")
                flush_chunk_size = 250

            pending_urls: list[str] = []
            pending_chunk_numbers: list[int] = []
            pending_contents: list[str] = []
            pending_metadatas: list[dict[str, Any]] = []
            delete_done = False
            deletion_urls = list(url_to_full_document.keys())

            async def flush_pending_chunks() -> None:
                nonlocal delete_done, chunks_stored
                if not pending_contents:
                    return

                storage_stats = await add_documents_to_supabase(
                    client=self.supabase_client,
                    urls=pending_urls,
                    chunk_numbers=pending_chunk_numbers,
                    contents=pending_contents,
                    metadatas=pending_metadatas,
                    url_to_full_document=url_to_full_document,
                    batch_size=25,
                    progress_callback=progress_callback,
                    enable_parallel_batches=True,
                    provider=None,
                    cancellation_check=cancellation_check,
                    url_to_page_id=url_to_page_id,
                    delete_existing_records=not delete_done,
                    deletion_urls=deletion_urls if not delete_done else None,
                )
                chunks_stored += storage_stats.get("chunks_stored", 0)
                delete_done = True

                pending_urls.clear()
                pending_chunk_numbers.clear()
                pending_contents.clear()
                pending_metadatas.clear()
                await asyncio.sleep(0)

            for doc_index, doc in enumerate(prepared_documents):
                if cancellation_check:
                    try:
                        cancellation_check()
                    except asyncio.CancelledError:
                        if progress_callback:
                            await progress_callback(
                                "cancelled",
                                99,
                                f"Chunking cancelled at document {doc_index + 1}/{len(prepared_documents)}",
                            )
                        raise

                doc_url = doc["url"]
                markdown_content = doc["markdown"]
                text_batches = storage_service.split_text_for_incremental_chunking(
                    markdown_content,
                    max_chars_per_batch=200_000,
                    pdf_pages_per_batch=75,
                )

                doc_chunk_index = 0
                for text_batch in text_batches:
                    chunks = await storage_service.smart_chunk_text_async(text_batch, chunk_size=5000)

                    for chunk in chunks:
                        if cancellation_check and doc_chunk_index % 10 == 0:
                            try:
                                cancellation_check()
                            except asyncio.CancelledError:
                                if progress_callback:
                                    await progress_callback(
                                        "cancelled",
                                        99,
                                        f"Chunking cancelled at chunk {doc_chunk_index + 1} of document {doc_index + 1}",
                                    )
                                raise

                        word_count = len(chunk.split())
                        pending_urls.append(doc_url)
                        pending_chunk_numbers.append(doc_chunk_index)
                        pending_contents.append(chunk)
                        pending_metadatas.append(
                            {
                                "url": doc_url,
                                "title": doc.get("title", ""),
                                "description": doc.get("description", ""),
                                "source_id": original_source_id,
                                "knowledge_type": request.get("knowledge_type", "documentation"),
                                "page_id": url_to_page_id.get(doc_url),
                                "crawl_type": crawl_type,
                                "word_count": word_count,
                                "char_count": len(chunk),
                                "chunk_index": doc_chunk_index,
                                "tags": request.get("tags", []),
                            }
                        )
                        chunk_count += 1
                        doc_chunk_index += 1

                        if len(pending_contents) >= flush_chunk_size:
                            await flush_pending_chunks()

                if doc_index > 0 and doc_index % 5 == 0:
                    await asyncio.sleep(0)

            await flush_pending_chunks()
        safe_logfire_info(f"url_to_full_document keys: {list(url_to_full_document.keys())[:5]}")

        avg_chunks = (chunk_count / processed_docs) if processed_docs > 0 else 0.0
        safe_logfire_info(
            f"Document storage | processed={processed_docs}/{len(crawl_results)} | chunks={chunk_count} | avg_chunks_per_doc={avg_chunks:.1f}"
        )

        return {
            "chunk_count": chunk_count,
            "chunks_stored": chunks_stored,
            "total_word_count": sum(source_word_counts.values()),
            "url_to_full_document": url_to_full_document,
            "source_id": original_source_id,
        }

    async def _create_source_records(
        self,
        all_metadatas: list[dict],
        all_contents: list[str],
        source_word_counts: dict[str, int],
        request: dict[str, Any],
        source_url: str | None = None,
        source_display_name: str | None = None,
    ):
        """
        Create or update source records in the database.

        Args:
            all_metadatas: List of metadata for all chunks
            all_contents: List of all chunk contents
            source_word_counts: Word counts per source_id
            request: Original crawl request
        """
        # Find ALL unique source_ids in the crawl results
        unique_source_ids = set()
        source_id_contents = {}
        source_id_word_counts = {}

        for i, metadata in enumerate(all_metadatas):
            source_id = metadata["source_id"]
            unique_source_ids.add(source_id)

            # Group content by source_id for better summaries
            if source_id not in source_id_contents:
                source_id_contents[source_id] = []
            source_id_contents[source_id].append(all_contents[i])

            # Track word counts per source_id
            if source_id not in source_id_word_counts:
                source_id_word_counts[source_id] = 0
            source_id_word_counts[source_id] += metadata.get('word_count', 0)

        safe_logfire_info(
            f"Found {len(unique_source_ids)} unique source_ids: {list(unique_source_ids)}"
        )

        # Create source records for ALL unique source_ids
        for source_id in unique_source_ids:
            # Get combined content for this specific source_id
            source_contents = source_id_contents[source_id]
            combined_content = ""
            for chunk in source_contents[:3]:  # First 3 chunks for this source
                if len(combined_content) + len(chunk) < 15000:
                    combined_content += " " + chunk
                else:
                    break

            # Generate summary with fallback
            try:
                # Call async extract_source_summary directly
                summary = await extract_source_summary(source_id, combined_content)
            except Exception as e:
                logger.error(f"Failed to generate AI summary for '{source_id}'", exc_info=True)
                safe_logfire_error(
                    f"Failed to generate AI summary for '{source_id}': {str(e)}, using fallback"
                )
                # Fallback to simple summary
                summary = f"Documentation from {source_id} - {len(source_contents)} pages crawled"

            # Update source info in database BEFORE storing documents
            safe_logfire_info(
                f"About to create/update source record for '{source_id}' (word count: {source_id_word_counts[source_id]})"
            )
            try:
                # Call async update_source_info directly
                await update_source_info(
                    client=self.supabase_client,
                    source_id=source_id,
                    summary=summary,
                    word_count=source_id_word_counts[source_id],
                    content=combined_content,
                    knowledge_type=request.get("knowledge_type", "documentation"),
                    tags=request.get("tags", []),
                    update_frequency=0,  # Set to 0 since we're using manual refresh
                    original_url=request.get("url"),  # Store the original crawl URL
                    source_url=source_url,
                    source_display_name=source_display_name,
                )
                safe_logfire_info(f"Successfully created/updated source record for '{source_id}'")
            except Exception as e:
                logger.error(f"Failed to create/update source record for '{source_id}'", exc_info=True)
                safe_logfire_error(
                    f"Failed to create/update source record for '{source_id}': {str(e)}"
                )
                # Try a simpler approach with minimal data
                try:
                    safe_logfire_info(f"Attempting fallback source creation for '{source_id}'")
                    fallback_data = {
                        "source_id": source_id,
                        "title": source_id,  # Use source_id as title fallback
                        "summary": summary,
                        "total_word_count": source_id_word_counts[source_id],
                        "metadata": {
                            "knowledge_type": request.get("knowledge_type", "documentation"),
                            "tags": request.get("tags", []),
                            "auto_generated": True,
                            "fallback_creation": True,
                            "original_url": request.get("url"),
                        },
                    }

                    # Add new fields if provided
                    if source_url:
                        fallback_data["source_url"] = source_url
                    if source_display_name:
                        fallback_data["source_display_name"] = source_display_name

                    self.supabase_client.table("archon_sources").upsert(fallback_data).execute()
                    safe_logfire_info(f"Fallback source creation succeeded for '{source_id}'")
                except Exception as fallback_error:
                    logger.error(f"Both source creation attempts failed for '{source_id}'", exc_info=True)
                    safe_logfire_error(
                        f"Both source creation attempts failed for '{source_id}': {str(fallback_error)}"
                    )
                    raise RuntimeError(
                        f"Unable to create source record for '{source_id}'. This will cause foreign key violations."
                    ) from fallback_error

        # Verify ALL source records exist before proceeding with document storage
        if unique_source_ids:
            for source_id in unique_source_ids:
                try:
                    source_check = (
                        self.supabase_client.table("archon_sources")
                        .select("source_id")
                        .eq("source_id", source_id)
                        .execute()
                    )
                    if not source_check.data:
                        raise Exception(
                            f"Source record verification failed - '{source_id}' does not exist in sources table"
                        )
                    safe_logfire_info(f"Source record verified for '{source_id}'")
                except Exception as e:
                    logger.error(f"Source verification failed for '{source_id}'", exc_info=True)
                    safe_logfire_error(f"Source verification failed for '{source_id}': {str(e)}")
                    raise

            safe_logfire_info(
                f"All {len(unique_source_ids)} source records verified - proceeding with document storage"
            )

    async def extract_and_store_code_examples(
        self,
        crawl_results: list[dict],
        url_to_full_document: dict[str, str],
        source_id: str,
        progress_callback: Callable | None = None,
        cancellation_check: Callable[[], None] | None = None,
        provider: str | None = None,
        embedding_provider: str | None = None,
    ) -> int:
        """
        Extract code examples from crawled documents and store them.

        Args:
            crawl_results: List of crawled documents
            url_to_full_document: Mapping of URLs to full document content
            source_id: The unique source_id for all documents
            progress_callback: Optional callback for progress updates
            cancellation_check: Optional function to check for cancellation
            provider: Optional LLM provider to use for code summaries
            embedding_provider: Optional embedding provider override for code example embeddings

        Returns:
            Number of code examples stored
        """
        result = await self.code_extraction_service.extract_and_store_code_examples(
            crawl_results,
            url_to_full_document,
            source_id,
            progress_callback,
            cancellation_check,
            provider,
            embedding_provider,
        )

        return result
