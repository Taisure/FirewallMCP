#!/usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = 'Taisue'
__copyright__ = 'Copyright © 2025/05/23, Banyu Tech Ltd.'

import requests
import os
from typing import Dict, Any, Optional, Generator, List, Union
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException


class OllamaError(Exception):
    """Base exception class for Ollama API errors"""
    pass

class Ollama:
    def __init__(self, base_url: str = "http://localhost:11434", api_key: Optional[str] = None):
        """
        Initialize Ollama client
        
        Args:
            base_url: Ollama server address (default: http://localhost:11434)
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = self._init_session()
    
    def _init_session(self) -> requests.Session:
        """Initialize requests session with retry logic"""
        session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[502, 503, 504],
        )
        session.mount("http://", HTTPAdapter(max_retries=retries))
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session
    
    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with authentication"""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    def _call_api(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
        files: Optional[Dict] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[requests.Response, Generator]:
        """Make API call with common parameters"""
        url = f"{self.base_url}/api/{endpoint.lstrip('/')}"
        headers = self._build_headers()
        
        try:
            response = self.session.request(
                method,
                url,
                headers=headers,
                json=json,
                files=files,
                stream=stream,
                **kwargs
            )
            response.raise_for_status()
            return response
        except RequestException as e:
            raise OllamaError(f"API request failed: {str(e)}") from e
    
    def _stream_handler(self, response: requests.Response) -> Generator:
        """Handle stream responses"""
        for line in response.iter_lines(chunk_size=1024):
            if line:
                try:
                    yield json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
    
    # ---------------------
    # Core API Endpoints
    # ---------------------
    
    def generate(
        self,
        model: str,
        prompt: str,
        options: Optional[Dict] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict, Generator]:
        """Generate text completion"""
        payload = {"model": model, "prompt": prompt}
        if options:
            for key, value in options.items():
                payload[key] = value
        return self._call_api("POST", "generate", json=payload, stream=stream)
    
    def chat(
        self,
        model: str,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        stream: bool = False,
        **kwargs
    ) -> Union[Dict, Generator]:
        """Generate chat completion"""
        payload = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools
        return self._call_api("POST", "chat", json=payload, stream=stream)
    
    def create_model(
        self,
        model: str,
        from_model: Optional[str] = None,
        files: Optional[Dict] = None,
        adapters: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """Create a new model"""
        payload = {"model": model}
        if from_model:
            payload["from"] = from_model
        if files:
            payload["files"] = files
        if adapters:
            payload["adapters"] = adapters
        return self._call_api("POST", "create", json={**payload, **kwargs})
    
    def list_models(self) -> Dict:
        """List available models"""
        return self._call_api("GET", "tags").json()
    
    def show_model(self, model: str, verbose: bool = False) -> Dict:
        """Show model information"""
        return self._call_api("POST", "show", json={"model": model, "verbose": verbose}).json()
    
    def copy_model(self, source: str, destination: str) -> Dict:
        """Copy an existing model"""
        return self._call_api("POST", "copy", json={"source": source, "destination": destination})
    
    def delete_model(self, model: str) -> Dict:
        """Delete a model"""
        return self._call_api("DELETE", "delete", json={"model": model})
    
    def pull_model(self, model: str, stream: bool = True) -> Union[Dict, Generator]:
        """Pull a model from the library"""
        return self._call_api("POST", "pull", json={"model": model}, stream=stream)
    
    def push_model(self, model: str, stream: bool = True) -> Union[Dict, Generator]:
        """Push a model to the library"""
        return self._call_api("POST", "push", json={"model": model}, stream=stream)
    
    def embed(self, model: str, input: Union[str, List[str]], **kwargs) -> Dict:
        """Generate embeddings"""
        payload = {"model": model, "input": input}
        return self._call_api("POST", "embed", json={**payload, **kwargs})
    
    def list_running_models(self) -> Dict:
        """List running models"""
        return self._call_api("GET", "ps").json()
    
    def version(self) -> Dict:
        """Get server version"""
        return self._call_api("GET", "version").json()
    
    # ---------------------
    # Blob Operations
    # ---------------------
    
    def push_blob(self, digest: str, file_path: str) -> None:
        """Upload a blob file"""
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            self._call_api("POST", f"blobs/{digest}", files=files)
    
    def check_blob_exists(self, digest: str) -> bool:
        """Check if blob exists"""
        try:
            self._call_api("HEAD", f"blobs/{digest}")
            return True
        except requests.HTTPError as e:
            return e.response.status_code == 404
    
    # ---------------------
    # Helper Methods
    # ---------------------
    
    def load_model(self, model: str, keep_alive: Optional[str] = None) -> Dict:
        """Load model into memory"""
        return self._call_api("POST", "generate", json={"model": model, "keep_alive": keep_alive})
    
    def unload_model(self, model: str) -> Dict:
        """Unload model from memory"""
        return self._call_api("POST", "generate", json={"model": model, "keep_alive": "0"})
    
    def get_model_stats(self, model: str) -> Dict:
        """Get model statistics"""
        return self.show_model(model)
    
    def generate_structured(
        self,
        model: str,
        prompt: str,
        schema: Dict,
        format: str = "json",
        **kwargs
    ) -> Dict:
        """Generate structured output"""
        payload = {
            "model": model,
            "prompt": prompt,
            "format": schema,
            "options": {"format": format}
        }
        return self._call_api("POST", "generate", json=payload)
    
    def chat_with_tools(
        self,
        model: str,
        messages: List[Dict],
        tools: List[Dict],
        **kwargs
    ) -> Union[Dict, Generator]:
        """Chat with tool support"""
        payload = {"model": model, "messages": messages, "tools": tools}
        return self._call_api("POST", "chat", json=payload, **kwargs)
