"""
Yandex Search API MCP Server - API Details

HTTP request handling for Yandex Search API v2.
Supports both synchronous and asynchronous (deferred) search modes.

Copyright © 2025 Yandex LLC. Licensed under Apache License 2.0.
"""

import os
import json
import base64
from typing import Dict, Any, Optional

import requests
from requests.exceptions import RequestException

# API Configuration
GEN_SEARCH_URL = "https://searchapi.api.cloud.yandex.net/v2/gen/search"
WEB_SEARCH_URL = "https://searchapi.api.cloud.yandex.net/v2/web/search"
OPERATIONS_URL = "https://searchapi.api.cloud.yandex.net/v1/operations"
DEFAULT_TIMEOUT = 30


def make_http_request(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    decode_base64: bool = False
) -> str:
    """
    Make an HTTP POST request to Yandex API.
    
    Args:
        url: The API endpoint URL.
        headers: HTTP headers.
        json_body: JSON request body.
        timeout: Request timeout in seconds.
        decode_base64: Whether to decode Base64 rawData from response.
        
    Returns:
        Response text or decoded XML.
        
    Raises:
        RuntimeError: If the request fails.
    """
    try:
        with requests.post(url, headers=headers, json=json_body, timeout=timeout) as response:
            response.raise_for_status()
            
            if decode_base64:
                decoded_data = base64.b64decode(json.loads(response.text)["rawData"]).decode('utf-8')
                return decoded_data
            return response.text
                
    except RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}") from e


def make_http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT
) -> str:
    """
    Make an HTTP GET request to Yandex API.
    
    Args:
        url: The API endpoint URL.
        headers: HTTP headers.
        timeout: Request timeout in seconds.
        
    Returns:
        Response text.
        
    Raises:
        RuntimeError: If the request fails.
    """
    try:
        with requests.get(url, headers=headers, timeout=timeout) as response:
            response.raise_for_status()
            return response.text
                
    except RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}") from e


def validate_input_data(data: Dict[str, Any], required_keys: set) -> Optional[str]:
    """
    Validate that all required keys are present in the data.
    
    Args:
        data: Input data dictionary.
        required_keys: Set of required key names.
        
    Returns:
        Error message if validation fails, None otherwise.
    """
    if missing_keys := required_keys - set(data):
        return f"Missing required keys: {', '.join(missing_keys)}"
    return None


def call_ai_search_with_yazeka(data: Dict[str, Any]) -> str:
    """
    Call the Yandex AI-powered generative search API.
    
    Args:
        data: Dictionary with 'query' and 'search_region' keys.
        
    Returns:
        Raw API response text.
    """
    api_key = os.getenv('SEARCH_API_KEY')
    folder_id = os.getenv('FOLDER_ID')
    if not api_key:
        raise ValueError("SEARCH_API_KEY environment variable not set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {api_key}"
    }
    body = {
        "messages": [{"content": data["query"], "role": "ROLE_USER" }],
        "searchFilters": [ { "lang": ("tr" if data["search_region"] == 'tr' else "en")} ],
        "folderId": folder_id,
        "fixMisspell": True,
        "enableNrfmDocs": True,
        "search_type": "SEARCH_TYPE_TR" if data["search_region"] == 'tr' else "SEARCH_TYPE_COM"
    }
    return make_http_request(GEN_SEARCH_URL, headers=headers, json_body=body, timeout=200)


def call_web_search(data: Dict[str, Any]) -> str:
    """
    Call the Yandex web search API in synchronous mode.
    
    Args:
        data: Dictionary with 'query' and 'search_region' keys.
        
    Returns:
        Decoded XML response.
    """
    api_key = os.getenv('SEARCH_API_KEY')
    folder_id = os.getenv('FOLDER_ID')
    if not api_key:
        raise ValueError("SEARCH_API_KEY environment variable not set")

    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Api-Key {api_key}"
    }

    body = {
        "query": {
            "searchType": "SEARCH_TYPE_TR" if data["search_region"] == 'tr' else "SEARCH_TYPE_COM",
            "queryText": data["query"],
            "familyMode": "FAMILY_MODE_NONE",
            "fixTypoMode": "FIX_TYPO_MODE_OFF",
        },
        "folderId": folder_id,
        "groupSpec": {"groupsOnPage": 4},
        "l10n": "LOCALIZATION_TR" if data["search_region"] == 'tr' else "LOCALIZATION_EN",
        "region": data["search_region"],
        "responseFormat": "FORMAT_XML"
    }

    return make_http_request(WEB_SEARCH_URL, headers=headers, json_body=body, timeout=10, decode_base64=True)


def call_web_search_async(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call the Yandex web search API in asynchronous (deferred) mode.
    
    Args:
        data: Dictionary with 'query' and 'search_region' keys.
        
    Returns:
        Operation object with 'id', 'done', 'createdAt', etc.
    """
    api_key = os.getenv('SEARCH_API_KEY')
    folder_id = os.getenv('FOLDER_ID')
    if not api_key:
        raise ValueError("SEARCH_API_KEY environment variable not set")

    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Api-Key {api_key}"
    }

    body = {
        "query": {
            "searchType": "SEARCH_TYPE_TR" if data["search_region"] == 'tr' else "SEARCH_TYPE_COM",
            "queryText": data["query"],
            "familyMode": "FAMILY_MODE_NONE",
            "fixTypoMode": "FIX_TYPO_MODE_OFF",
        },
        "folderId": folder_id,
        "groupSpec": {"groupsOnPage": 4},
        "l10n": "LOCALIZATION_TR" if data["search_region"] == 'tr' else "LOCALIZATION_EN",
        "region": data["search_region"],
        "responseFormat": "FORMAT_XML",
        "mode": "MODE_ASYNC"
    }

    response_text = make_http_request(WEB_SEARCH_URL, headers=headers, json_body=body, timeout=10)
    return json.loads(response_text)


def get_operation(operation_id: str) -> Dict[str, Any]:
    """
    Get the status and result of an async operation.
    
    Args:
        operation_id: The Yandex operation ID.
        
    Returns:
        Operation object with 'id', 'done', 'response', etc.
    """
    api_key = os.getenv('SEARCH_API_KEY')
    if not api_key:
        raise ValueError("SEARCH_API_KEY environment variable not set")

    headers = {
        "Authorization": f"Api-Key {api_key}"
    }

    url = f"{OPERATIONS_URL}/{operation_id}"
    response_text = make_http_get(url, headers=headers, timeout=10)
    return json.loads(response_text)


def decode_operation_result(operation: Dict[str, Any]) -> Optional[str]:
    """
    Decode the result from a completed operation.
    
    Args:
        operation: The operation object from get_operation().
        
    Returns:
        Decoded XML/HTML string, or None if not available.
    """
    if not operation.get('done'):
        return None
    
    response = operation.get('response', {})
    raw_data = response.get('rawData')
    
    if raw_data:
        return base64.b64decode(raw_data).decode('utf-8')
    
    return None
