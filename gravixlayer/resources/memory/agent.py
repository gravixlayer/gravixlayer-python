"""
Memory inference agent for analyzing conversations and extracting memories
"""
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from .types import MemoryType


class MemoryAgent:
    """
    Intelligent agent that analyzes conversations and extracts meaningful memories
    Provides semantic memory inference capabilities
    """
    
    def __init__(self, client, model: str = "mistralai/mistral-nemo-instruct-2407"):
        """
        Initialize the memory agent
        
        Args:
            client: GravixLayer client for LLM calls
            model: LLM model to use for inference
        """
        self.client = client
        self.model = model
        self.inference_prompt = self._get_inference_prompt()
    
    def _get_inference_prompt(self) -> str:
        """Get the system prompt for memory inference"""
        return """You are a memory extraction agent. Analyze conversations and extract meaningful memories about users.

Memory Types:
- FACTUAL: Long-term structured knowledge (preferences, attributes, settings)
- EPISODIC: Specific past conversations or events (historical interactions)
- WORKING: Short-term context for current session (temporary information)
- SEMANTIC: Generalized knowledge from patterns (learned behaviors)

Extract memories in this JSON format:
{
  "memories": [
    {
      "content": "Clear, concise memory statement",
      "type": "FACTUAL|EPISODIC|WORKING|SEMANTIC",
      "importance": 0.1-1.0,
      "metadata": {
        "category": "preference|interaction|context|pattern",
        "confidence": 0.1-1.0,
        "topics": ["topic1", "topic2"]
      }
    }
  ]
}

Rules:
1. Extract only meaningful, actionable memories
2. Focus on user preferences, behaviors, and important facts
3. Avoid redundant or trivial information
4. Use clear, specific language
5. Assign appropriate memory types and importance scores
6. Include relevant metadata for filtering

Analyze the conversation and extract memories:"""

    async def infer_memories(self, messages: List[Dict[str, str]], user_id: str) -> List[Dict[str, Any]]:
        """
        Analyze conversation messages and infer memories
        
        Args:
            messages: List of conversation messages with 'role' and 'content'
            user_id: User identifier
            
        Returns:
            List of inferred memory dictionaries
        """
        try:
            # Format conversation for analysis
            conversation = self._format_conversation(messages)
            
            # Create inference prompt
            full_prompt = f"{self.inference_prompt}\n\nConversation:\n{conversation}"
            
            # Call LLM for inference using same GravixLayer client and API key
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.inference_prompt},
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
                return []
            
            # Process and validate memories
            processed_memories = []
            for memory_data in memories_data["memories"]:
                if self._validate_memory(memory_data):
                    processed_memories.append({
                        "content": memory_data["content"],
                        "memory_type": MemoryType(memory_data["type"].lower()),
                        "importance_score": memory_data.get("importance", 1.0),
                        "metadata": {
                            **memory_data.get("metadata", {}),
                            "inferred": True,
                            "user_id": user_id,
                            "source": "conversation_analysis"
                        }
                    })
            
            return processed_memories
            
        except Exception as e:
            print(f"Memory inference error: {e}")
            return []
    
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
        
        # Validate memory type
        valid_types = ["factual", "episodic", "working", "semantic"]
        if memory_data["type"].lower() not in valid_types:
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
        
        # Optionally create individual message memories
        for i, msg in enumerate(messages):
            if msg.get("role") == "user":  # Focus on user messages
                memories.append({
                    "content": f"User said: {msg.get('content', '')}",
                    "memory_type": MemoryType.EPISODIC,
                    "importance_score": 0.6,
                    "metadata": {
                        "category": "user_message",
                        "message_index": i,
                        "inferred": False,
                        "user_id": user_id,
                        "source": "raw_storage"
                    }
                })
        
        return memories