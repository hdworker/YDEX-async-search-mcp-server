"""
Yandex Search API MCP Server

This module implements an MCP server providing access to Yandex Search API v2 features:
- Web search (sync and async modes)
- AI-powered search (sync only)
- Operation status tracking
- SQLite storage for operation IDs

Copyright © 2025 Yandex LLC. Licensed under Apache License 2.0.

Features:
- FastMCP integration
- Input validation
- Error handling
- Configuration via environment variables
- Async mode with SQLite storage for cost optimization
"""

import json
import os
import re
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP
from detail import (
    validate_input_data,
    call_ai_search_with_yazeka,
    call_web_search,
    call_web_search_async,
    get_operation,
    decode_operation_result
)
from storage import get_storage

# Create an MCP server
mcp = FastMCP(
    name="Yandex Search Api v2, web and generation (async mode)"
)

# Initialize storage
storage = get_storage()


@mcp.tool()
def ai_search_with_yazeka(body: dict) -> str:
    """
    Use this tool when the user needs to search online, the search query is complex, and a short summary of the web search results 
    will make the answer easier to understand. Always call this tool if the user explicitely asks to search with yazeka.

    Args:
        body (dict): Required. input containing:
            - query: Required. search query string. Can contain a question and keywords
            - search_region: Required. Search region. Valid values: 'tr' - Turkish region, 'en' - English region

        minimal example: "body": {
                                "query": "Who won the most recent Formula 1 race in 2025?",
                                "search_region": "tr"
                         }

    Returns:
        dict: array of data and source
    """
    data = body
    required_keys = {"query", "search_region"}
    if error_message := validate_input_data(data, required_keys):
        return error_message

    api_response = json.loads(call_ai_search_with_yazeka(data)[1:-1])
    response = dict()
    response["response"] = api_response["message"]["content"]
    response["sources"] = [source["url"] for source in api_response["sources"] if source["used"]]

    return json.dumps(response, ensure_ascii=False, indent=2)


def extract_documents_from_xml(xml_content):
    """Extract individual documents from XML content."""
    doc_strings = []
    lines = xml_content.split('\n')
    current_doc = []
    in_doc = False
    
    for line in lines:
        if '<doc ' in line and 'id=' in line:
            in_doc = True
            current_doc = [line]
        elif in_doc and '</doc>' in line:
            current_doc.append(line)
            doc_strings.append('\n'.join(current_doc))
            in_doc = False
        elif in_doc:
            current_doc.append(line)
    
    return doc_strings


def clean_text(text):
    """Clean text from hlword tags."""
    if not text:
        return ""
    cleaned = re.sub(r'<hlword>|</hlword>', '', text)
    return cleaned.strip()


def extract_document_elements(doc_string):
    """Extract elements from document string."""
    url_match = re.search(r'<url>(.*?)</url>', doc_string)
    headline_match = re.search(r'<headline>(.*?)</headline>', doc_string)
    title_match = re.search(r'<title>(.*?)</title>', doc_string)
    passage_matches = re.findall(r'<passage>(.*?)</passage>', doc_string)
    extended_text_match = re.search(r'<extended-text>(.*?)</extended-text>', doc_string)
    
    return {
        'url': url_match.group(1) if url_match else None,
        'headline': headline_match.group(1) if headline_match else None,
        'title': title_match.group(1) if title_match else None,
        'passages': passage_matches,
        'extended_text': extended_text_match.group(1) if extended_text_match else None
    }


def get_best_content(elements):
    """Select the best content from available elements."""
    if elements['headline']:
        return clean_text(elements['headline']), "headline"
    elif elements['title']:
        return clean_text(elements['title']), "title"
    elif elements['passages']:
        cleaned_passages = [clean_text(p) for p in elements['passages'] if p]
        return " ".join(cleaned_passages), "passages"
    elif elements['extended_text']:
        return clean_text(elements['extended_text']), "extended-text"
    else:
        return None, None


def process_single_document(doc_string):
    """Process a single document and return the result."""
    elements = extract_document_elements(doc_string)
    
    if not elements['url']:
        return None
    
    content, source = get_best_content(elements)
    
    if content:
        return {
            'data': content,
            'source': elements['url']
        }
    
    return None


@mcp.tool()
def web_search(body: dict) -> str:
    """
    Perform a web search using Yandex Search API.
    
    Supports both synchronous and asynchronous modes.
    
    Args:
        body (dict): Required. Input containing:
            - query: Required. Search query string (max 400 chars).
            - search_region: Required. Search region: 'ru' - Russian, 'tr' - Turkish, 'en' - English.
            - mode: Optional. 'sync' (default) or 'async' for deferred execution.
            - wait: Optional. If true, wait for async result (default: false).
            
        minimal example: {
            "query": "кофемашина",
            "search_region": "ru"
        }
        
        async example: {
            "query": "кофемашина",
            "search_region": "ru",
            "mode": "async"
        }

    Returns:
        For sync mode: dict with search results.
        For async mode: dict with operation_id for later retrieval.
        
    Note:
        Async mode is cheaper (30.5₽ vs 488₽ per 1000 requests).
        Use get_search_status to retrieve results later.
    """
    data = body
    required_keys = {"query", "search_region"}
    if error_message := validate_input_data(data, required_keys):
        return error_message

    mode = data.get("mode", "sync")
    wait = data.get("wait", False)
    
    if mode == "async":
        # Async mode - send deferred request
        operation = call_web_search_async(data)
        operation_id = operation.get("id")
        
        # Save to storage
        folder_id = os.getenv('FOLDER_ID', '')
        storage.save(operation_id, data["query"], folder_id)
        
        # If wait is true, poll until done
        if wait and not operation.get("done"):
            import time
            max_wait = 60  # seconds
            start_time = time.time()
            
            while not operation.get("done") and (time.time() - start_time) < max_wait:
                time.sleep(1)
                operation = get_operation(operation_id)
            
            if operation.get("done"):
                result = decode_operation_result(operation)
                storage.update_result(operation_id, "COMPLETED", result)
                
                # Parse and return results
                if result:
                    doc_strings = extract_documents_from_xml(result)
                    response = {'operation_id': operation_id, 'status': 'COMPLETED', 'responses': []}
                    for doc_string in doc_strings:
                        doc_result = process_single_document(doc_string)
                        if doc_result:
                            response["responses"].append(doc_result)
                    return json.dumps(response, ensure_ascii=False, indent=2)
        
        return json.dumps({
            "operation_id": operation_id,
            "status": "PENDING",
            "message": "Request queued. Use get_search_status to check result."
        }, ensure_ascii=False, indent=2)
    
    else:
        # Sync mode - original behavior
        decoded_data = call_web_search(data)
        doc_strings = extract_documents_from_xml(decoded_data)
        response = {'responses': []}

        for doc_string in doc_strings:
            doc_result = process_single_document(doc_string)
            if doc_result:
                response["responses"].append(doc_result)
        
        return json.dumps(response, ensure_ascii=False, indent=2)


@mcp.tool()
def get_search_status(body: dict) -> str:
    """
    Get the status and result of an async search operation.
    
    Args:
        body (dict): Required. Input containing:
            - operation_id: Required. The operation ID from web_search async call.
            
        minimal example: {
            "operation_id": "abc123-def456"
        }

    Returns:
        dict with operation status and results (if completed).
        
    Note:
        Operations are stored in local SQLite database.
        Results are available for 7 days after completion.
    """
    data = body
    required_keys = {"operation_id"}
    if error_message := validate_input_data(data, required_keys):
        return error_message

    operation_id = data["operation_id"]
    
    # First check local storage
    local_op = storage.get(operation_id)
    
    # Then check Yandex API
    try:
        operation = get_operation(operation_id)
    except Exception as e:
        return json.dumps({
            "operation_id": operation_id,
            "status": "ERROR",
            "error": str(e)
        }, ensure_ascii=False, indent=2)
    
    if operation.get("done"):
        result = decode_operation_result(operation)
        storage.update_result(operation_id, "COMPLETED", result)
        
        # Parse and return results
        if result:
            doc_strings = extract_documents_from_xml(result)
            response = {
                'operation_id': operation_id,
                'status': 'COMPLETED',
                'created_at': operation.get('createdAt'),
                'completed_at': operation.get('modifiedAt'),
                'responses': []
            }
            for doc_string in doc_strings:
                doc_result = process_single_document(doc_string)
                if doc_result:
                    response["responses"].append(doc_result)
            return json.dumps(response, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "operation_id": operation_id,
                "status": "COMPLETED",
                "created_at": operation.get('createdAt'),
                "completed_at": operation.get('modifiedAt'),
                "result": None
            }, ensure_ascii=False, indent=2)
    else:
        storage.update_result(operation_id, "PENDING")
        return json.dumps({
            "operation_id": operation_id,
            "status": "PENDING",
            "created_at": operation.get('createdAt'),
            "message": "Operation still processing. Check again later."
        }, ensure_ascii=False, indent=2)


@mcp.tool()
def get_pending_searches(body: dict) -> str:
    """
    Get all pending async search operations.
    
    Args:
        body (dict): Optional. Input containing:
            - limit: Optional. Max results to return (default: 100).
            
        minimal example: {}

    Returns:
        dict with list of pending operations.
    """
    data = body if body else {}
    limit = data.get("limit", 100)
    
    pending = storage.get_pending()
    
    return json.dumps({
        "count": len(pending),
        "operations": pending[:limit]
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def cleanup_old_searches(body: dict) -> str:
    """
    Clean up old search operations from local storage.
    
    Args:
        body (dict): Optional. Input containing:
            - days: Optional. Delete operations older than N days (default: 7).
            
        minimal example: {}

    Returns:
        dict with cleanup statistics.
    """
    data = body if body else {}
    days = data.get("days", 7)
    
    deleted = storage.cleanup(days)
    stats = storage.count_by_status()
    
    return json.dumps({
        "deleted_count": deleted,
        "remaining_by_status": stats
    }, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        raise
