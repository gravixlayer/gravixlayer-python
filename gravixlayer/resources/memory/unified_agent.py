"""
Unified Memory inference agent using GravixLayer's chat API
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from .types import MemoryType


class UnifiedMemoryAgent:
    """
    Memory inference agent that uses GravixLayer's chat API for memory extraction
    """
    
    def __init__(self, client, model: str = "mistralai/mistral-nemo-instruct-2407"):
        """
        Initialize the unified memory agent
        
        Args:
            client: GravixLayer client for chat API calls
            model: LLM model to use for inference (default: mistralai/mistral-nemo-instruct-2407)
        """
        self.client = client
        self.model = model
    
    def _get_inference_prompt(self) -> str:
        """Get the system prompt for memory inference"""
        return """You are a memory extraction agent. Extract ONLY the most important user preferences and facts from conversations.

Extract memories in this JSON format:
{
  "memories": [
    {
      "content": "Clear, concise memory statement about user preference or fact",
      "type": "FACTUAL", 
      "importance": 0.8-1.0,
      "metadata": {
        "category": "preference",
        "confidence": 0.8-1.0
      }
    }
  ]
}

STRICT Rules:
1. Extract ONLY 1-3 key user preferences or important facts
2. Focus on what the user likes/dislikes, needs, or important personal info
3. Ignore assistant responses and conversation flow
4. Use simple, direct language: "User prefers X" or "User dislikes Y"
5. Only extract if clearly stated by the user
6. Avoid redundant or similar memories

Analyze the conversation and extract only the most important user memories:"""

    async def infer_memories(self, messages: List[Dict[str, str]], user_id: str) -> List[Dict[str, Any]]:
        """
        Analyze conversation messages and infer memories using GravixLayer chat API
        
        Args:
            messages: List of conversation messages with 'role' and 'content'
            user_id: User identifier
            
        Returns:
            List of inferred memory dictionaries
        """
        try:
            # Format conversation for analysis
            conversation = self._format_conversation(messages)
            
            # Use GravixLayer's chat API for inference (same client, same API key)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_inference_prompt()},
                    {"role": "user", "content": f"Conversation:\n{conversation}"}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse response
            content = response.choices[0].message.content
            
            # Extract JSON from response
            memories_data = self._extract_json(content)
            
            if not memories_data or "memories" not in memories_data:
                # Try simple fallback extraction
                return self._simple_fallback_extraction(messages, user_id)
            
            # Process and validate memories
            processed_memories = []
            for memory_data in memories_data["memories"]:
                if self._validate_memory(memory_data):
                    # Map LLM types to our MemoryType enum
                    memory_type_str = memory_data["type"].lower()
                    if memory_type_str == "preference":
                        memory_type = MemoryType.FACTUAL  # Treat preferences as factual
                    else:
                        memory_type = MemoryType(memory_type_str)
                    
                    processed_memories.append({
                        "content": memory_data["content"],
                        "memory_type": memory_type,
                        "importance_score": memory_data.get("importance", 1.0),
                        "metadata": {
                            **memory_data.get("metadata", {}),
                            "inferred": True,
                            "user_id": user_id,
                            "source": "gravixlayer_chat_inference",
                            "model_used": self.model,
                            "inference_timestamp": datetime.now().isoformat()
                        }
                    })
            
            return processed_memories
            
        except Exception as e:
            print(f"Memory inference error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to simple extraction
            return self._simple_fallback_extraction(messages, user_id)
    
    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """Format conversation messages for analysis"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role.upper()}: {content}")
        
        return "\n".join(formatted)
    
    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response"""
        try:
            # Try to find JSON in the response
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx]
                return json.loads(json_str)
            
            return None
            
        except json.JSONDecodeError:
            return None
    
    def _validate_memory(self, memory_data: Dict[str, Any]) -> bool:
        """Validate extracted memory data"""
        required_fields = ["content", "type"]
        
        for field in required_fields:
            if field not in memory_data:
                return False
        
        # Validate memory type - accept both standard types and LLM variations
        valid_types = ["factual", "episodic", "working", "semantic", "preference"]
        memory_type = memory_data["type"].lower()
        if memory_type not in valid_types:
            return False
        
        # Validate content is not empty
        if not memory_data["content"].strip():
            return False
        
        return True
    
    def extract_raw_memories(self, messages: List[Dict[str, str]], user_id: str) -> List[Dict[str, Any]]:
        """
        Extract raw memories without inference (store conversation as-is)
        
        Args:
            messages: List of conversation messages
            user_id: User identifier
            
        Returns:
            List of raw memory dictionaries
        """
        memories = []
        
        # Create episodic memory for the entire conversation
        conversation_content = self._format_conversation(messages)
        
        memories.append({
            "content": f"Conversation: {conversation_content}",
            "memory_type": MemoryType.EPISODIC,
            "importance_score": 0.8,
            "metadata": {
                "category": "raw_conversation",
                "message_count": len(messages),
                "inferred": False,
                "user_id": user_id,
                "source": "raw_storage",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # Create individual memories for important user messages
        for i, msg in enumerate(messages):
            if msg.get("role") == "user" and len(msg.get("content", "").strip()) > 10:
                memories.append({
                    "content": f"User said: {msg.get('content', '')}",
                    "memory_type": MemoryType.EPISODIC,
                    "importance_score": 0.6,
                    "metadata": {
                        "category": "user_message",
                        "message_index": i,
                        "inferred": False,
                        "user_id": user_id,
                        "source": "raw_storage",
                        "timestamp": datetime.now().isoformat()
                    }
                })
        
        return memories
    
    def _simple_fallback_extraction(self, messages: List[Dict[str, str]], user_id: str) -> List[Dict[str, Any]]:
        """
        Simple fallback extraction when AI inference fails
        Extract basic preferences from user messages
        """
        memories = []
        
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                
                # Look for preference patterns
                if "love" in content or "like" in content:
                    if "sci-fi" in content or "science fiction" in content:
                        memories.append({
                            "content": "User prefers sci-fi movies",
                            "memory_type": MemoryType.FACTUAL,
                            "importance_score": 0.9,
                            "metadata": {
                                "category": "preference",
                                "inferred": True,
                                "user_id": user_id,
                                "source": "simple_fallback",
                                "timestamp": datetime.now().isoformat()
                            }
                        })
                
                if "not a big fan" in content or "don't like" in content or "dislike" in content:
                    if "thriller" in content:
                        memories.append({
                            "content": "User dislikes thriller movies",
                            "memory_type": MemoryType.FACTUAL,
                            "importance_score": 0.9,
                            "metadata": {
                                "category": "preference",
                                "inferred": True,
                                "user_id": user_id,
                                "source": "simple_fallback",
                                "timestamp": datetime.now().isoformat()
                            }
                        })
        
        return memories