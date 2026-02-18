"""
Download Handler Helper

Provides fallback support for downloadable document URLs (e.g. endpoints that
trigger file downloads instead of returning HTML).
"""

import os
from typing import Any

import requests

from ....config.logfire_config import get_logger
from ....utils.document_processing import extract_text_from_document
from .url_handler import URLHandler

logger = get_logger(__name__)


def try_extract_downloadable_document(url: str, timeout: int = 45) -> dict[str, Any] | None:
    """
    Try to download and extract text from a document URL.

    Args:
        url: Source URL that may trigger a download
        timeout: Request timeout in seconds

    Returns:
        Crawl-result-like dictionary if extraction succeeds, otherwise None
    """
    headers = {
        "User-Agent": "ArchonCrawler/1.0",
        "Accept": "application/pdf,application/octet-stream,text/plain,*/*",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        logger.warning(f"Download fallback failed for {url}: {exc}")
        return None

    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
    content_disposition = (response.headers.get("content-disposition") or "").lower()

    final_url = response.url or url
    inferred_name = URLHandler.infer_filename_from_url(final_url)

    is_pdf = (
        content_type == "application/pdf"
        or inferred_name.lower().endswith(".pdf")
        or final_url.lower().endswith(".pdf")
        or ".pdf" in content_disposition
    )

    if not is_pdf:
        logger.debug(
            f"Download fallback skipped non-PDF content | url={url} | final_url={final_url} | content_type={content_type}"
        )
        return None

    body = response.content
    if not body:
        logger.warning(f"Download fallback returned empty body | url={url}")
        return None

    try:
        extracted_text = extract_text_from_document(body, inferred_name, content_type or "application/pdf")
    except Exception as exc:
        logger.warning(f"Failed to extract downloaded PDF text for {url}: {exc}")
        return None

    cleaned_text = extracted_text.strip()
    if not cleaned_text:
        logger.warning(f"Downloaded PDF had no extractable text | url={url}")
        return None

    title = os.path.splitext(os.path.basename(inferred_name))[0] or "Downloaded Document"

    return {
        "url": url,
        "markdown": cleaned_text,
        "html": "",
        "title": title,
        "content_type": "application/pdf",
        "download_url": final_url,
    }
