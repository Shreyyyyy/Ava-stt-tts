"""
Ollama client for local LLM integration with AVA
"""

import logging
import asyncio
import json
from typing import Optional, List, Dict, Any

try:
    import ollama
except ImportError:
    ollama = None

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for interacting with local Ollama LLM"""
    
    def __init__(self, model_name: str = "llama3.2:latest", host: str = "http://127.0.0.1:11434"):
        self.model_name = model_name
        self.host = host
        self.client = ollama if ollama else None
        
        if not self.client:
            logger.error("Ollama library not installed. Install with: pip install ollama")
            raise ImportError("Ollama library not available")
    
    def is_available(self) -> bool:
        """Check if Ollama is available and model is pulled"""
        try:
            if not self.client:
                logger.error("Ollama client not initialized")
                return False
            
            # Check if Ollama is running and get models
            try:
                # Use the client with our host
                from ollama import Client as OllamaAPIClient
                client = OllamaAPIClient(host=self.host)
                models_response = client.list()
                if not models_response or not models_response.models:
                    logger.warning("No models found in Ollama")
                    return False
                
                # Extract model names from ListResponse object
                available_models = []
                for model in models_response.models:
                    if hasattr(model, 'model'):
                        available_models.append(model.model)
                    elif hasattr(model, 'name'):
                        available_models.append(model.name)
                    elif isinstance(model, str):
                        available_models.append(model)
                
                logger.info(f"Available Ollama models: {available_models}")
                return self.model_name in available_models
                
            except Exception as model_error:
                logger.error(f"Error getting Ollama models: {model_error}")
                return False
                
        except Exception as e:
            logger.error(f"Ollama availability check failed: {e}")
            return False
    
    def generate_response(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7
    ) -> str:
        """Generate response from local LLM"""
        try:
            logger.info(f"Generating LLM response: prompt='{prompt[:100]}...'")
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            # Use the client with our host
            from ollama import Client as OllamaAPIClient
            client = OllamaAPIClient(host=self.host)
            
            # Generate response
            response = client.chat(
                model=self.model_name,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            )
            
            if response and 'message' in response:
                llm_response = response['message']['content']
                logger.info(f"LLM response generated: '{llm_response[:100]}...'")
                return llm_response
            else:
                logger.error("Invalid response from Ollama")
                return "I'm sorry, I couldn't generate a response."
                
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return "I'm experiencing technical difficulties. Please try again."
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        try:
            models = self.client.list()
            for model in models:
                if model['name'] == self.model_name:
                    return model
            return {}
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {}

# System prompts for different contexts
AVA_SYSTEM_PROMPT = """You are AVA, a helpful AI voice assistant specializing in Indian languages and culture. 
You are friendly, professional, and culturally aware.

Guidelines:
- Be helpful and conversational
- Show respect for Indian culture and values
- Keep responses concise but informative
- Use simple, clear language
- If asked about Indian topics, provide culturally relevant information
- Respond in the same language as the user when possible

You have access to text-to-speech and speech-to-text capabilities for Indian languages."""
