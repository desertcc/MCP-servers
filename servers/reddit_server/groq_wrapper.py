#!/usr/bin/env python3
"""
Wrapper for Groq API to handle different environments and versions
"""

import os
import sys
import logging
import traceback
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class GroqWrapper:
    """Wrapper for Groq API to handle different environments and versions"""
    
    def __init__(self, api_key=None):
        """Initialize the Groq wrapper"""
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.client = None
        self.initialize()
    
    def initialize(self):
        """Initialize the Groq client with error handling for different environments"""
        if not self.api_key:
            logger.error("GROQ_API_KEY is not set")
            return
            
        try:
            import groq
            logger.info(f"Groq version: {groq.__version__}")
            
            # Method 1: Standard initialization with try/except for proxies
            try:
                self.client = groq.Groq(api_key=self.api_key)
                logger.info("Successfully initialized Groq client with standard method")
                return
            except TypeError as e:
                if "proxies" in str(e):
                    logger.warning("Standard initialization failed due to proxies parameter")
                else:
                    logger.error(f"Standard initialization failed: {e}")
            
            # Method 2: Try to monkey patch the client to avoid proxies issue
            try:
                # Import the internal modules
                from groq._client import Groq as GroqClient
                from groq._base_client import SyncHttpxClientWrapper
                
                # Create a custom initialization that avoids the proxies parameter
                class CustomHttpWrapper(SyncHttpxClientWrapper):
                    def __init__(self, **kwargs):
                        # Remove 'proxies' if it exists in kwargs
                        if 'proxies' in kwargs:
                            del kwargs['proxies']
                        super().__init__(**kwargs)
                
                # Initialize with our custom wrapper
                self.client = GroqClient(
                    api_key=self.api_key,
                    http_client=CustomHttpWrapper()
                )
                logger.info("Successfully initialized Groq client with custom HTTP wrapper")
                return
            except Exception as e:
                logger.error(f"Custom initialization failed: {e}")
            
            # Method 3: Direct HTTP requests as last resort
            try:
                import requests
                import json
                
                class FallbackGroqClient:
                    def __init__(self, api_key):
                        self.api_key = api_key
                        self.chat = self.ChatCompletions(api_key)
                    
                    class ChatCompletions:
                        def __init__(self, api_key):
                            self.api_key = api_key
                        
                        def create(self, **kwargs):
                            url = "https://api.groq.com/openai/v1/chat/completions"
                            headers = {
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json"
                            }
                            
                            # Convert max_tokens to max_completion_tokens if needed
                            if "max_tokens" in kwargs and "max_completion_tokens" not in kwargs:
                                kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                            
                            response = requests.post(url, headers=headers, json=kwargs)
                            response.raise_for_status()
                            
                            # Parse the response
                            result = response.json()
                            
                            # Create a response object that mimics the Groq API
                            class Choice:
                                def __init__(self, message):
                                    self.message = type('Message', (), {'content': message['content']})
                            
                            class Response:
                                def __init__(self, choices):
                                    self.choices = [Choice(choice['message']) for choice in choices]
                            
                            return Response(result['choices'])
                
                self.client = FallbackGroqClient(self.api_key)
                logger.info("Successfully initialized Groq client with fallback HTTP method")
                return
            except Exception as e:
                logger.error(f"Fallback initialization failed: {e}")
                logger.error(traceback.format_exc())
        
        except Exception as e:
            logger.error(f"Failed to import or initialize Groq: {e}")
            logger.error(traceback.format_exc())
    
    def generate_completion(self, prompt_or_messages, model="llama3-8b-8192", max_tokens=300, temperature=0.7):
        """Generate a completion using the Groq API
        
        Args:
            prompt_or_messages: Either a string prompt or a list of message dictionaries
            model: The Groq model to use
            max_tokens: Maximum number of tokens to generate
            temperature: Temperature for generation (higher = more creative)
        """
        if not self.client:
            logger.warning("Groq client is not available, using fallback response")
            return "This looks great! Thanks for sharing your work!"
        
        try:
            # Determine if prompt_or_messages is a string prompt or a messages array
            if isinstance(prompt_or_messages, str):
                # If it's a string, use the default message structure
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a POSITIVE and SUPPORTIVE Reddit commenter. Keep replies super brief (1-2 sentences, max 25 words). "
                            "Your replies MUST be warm, encouraging, and helpful - never confused, dismissive, or negative. "
                            "Sound casual and warm like a fellow Redditor - not formal. Use conversational tone. "
                            "No quotes, no greetings, no summarizing. If unsure, be generally positive about creativity or sharing."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt_or_messages
                    }
                ]
            else:
                # If it's already a messages array, use it directly
                messages = prompt_or_messages
            
            # Log what we're sending to Groq
            logger.info(f"Sending request to Groq model: {model}")
            
            completion = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            reply = completion.choices[0].message.content.strip()
            logger.info(f"Generated reply: {reply}")
            return reply
        except Exception as e:
            logger.error(f"Error generating completion: {e}")
            logger.error(traceback.format_exc())
            return "This looks great! Thanks for sharing your work!"

# Test the wrapper if run directly
if __name__ == "__main__":
    groq_wrapper = GroqWrapper()
    if groq_wrapper.client:
        response = groq_wrapper.generate_completion("Say hello!")
        print(f"Response: {response}")
    else:
        print("Failed to initialize Groq client")
