"""
Synchronous Memory Agent for AI inference in sync mode
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from .types import MemoryType


class SyncMemoryAgent:
    """
    Synchronous memory agent that can infer memories from conversations using LLM API
    """
    
    def __init__(self, client, inference_model: str = "mistralai/mistral-nemo-instruct-2407"):
        """
        Initialize sync memory agent
        
        Args:
            client: GravixLayer sync client instance
            inference_model: Model to use for memory inference
        """
        self.client = client
        self.inference_model = inference_model
    
    def infer_memories(self, messages: List[Dict[str, str]], user_id: str) -> List[Dict[str, Any]]:
        """
        Synchronously infer memories from conversation messages using LLM
        
        Args:
            messages: List of conversation messages
            user_id: User identifier
            
        Returns:
            List of inferred memory data
        """
        try:
            # Format conversation for the LLM
            conversation = self._format_conversation(messages)
            
            # Create prompt for memory extraction
            prompt = self._create_memory_extraction_prompt(conversation, user_id)
            
            # Call LLM synchronously
            response = self.client.chat.completions.create(
                model=self.inference_model,
                messages=[
                    {"role": "system", "content": "You are a memory extraction assistant. Extract important memories from conversations and return them as JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse the response
            content = response.choices[0].message.content
            memories = self._parse_memory_response(content, user_id)
            
            return memories
            
        except Exception as e:
            print(f"Memory inference failed: {e}")
            # Fallback to raw storage
            return self.extract_raw_memories(messages, user_id)
    
    def extract_raw_memories(self, messages: List[Dict[str, str]], user_id: str) -> List[Dict[str, Any]]:
        """
        Extract raw memories without AI inference (fallback)
        
        Args:
            messages: List of conversation messages
            user_id: User identifier
            
        Returns:
            List of raw memory data
        """
        conversation = self._format_conversation(messages)
        
        return [{
            "content": f"Conversation: {conversation}",
            "memory_type": MemoryType.EPISODIC,
            "metadata": {
                "category": "raw_conversation",
                "message_count": len(messages),
                "inferred": False,
                "source": "raw_storage",
                "timestamp": datetime.now().isoformat()
            }
        }]
    
    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """Format conversation messages into a readable string"""
        formatted = []
        for msg in messages:
            role = msg.get('role', 'unknown').upper()
            content = msg.get('content', '')
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)
    
    def _create_memory_extraction_prompt(self, conversation: str, user_id: str) -> str:
        """Create prompt for memory extraction"""
        return f"""
Extract important memories from this conversation for user {user_id}.

Conversation:
{conversation}

Extract memories that are:
1. User preferences (likes, dislikes, interests)
2. Personal facts (job, location, family)
3. Important decisions or plans
4. Behavioral patterns

Return a JSON array of memories in this format:
[
  {{
    "content": "extracted memory text",
    "memory_type": "factual|episodic|semantic",
    "importance": 0.1-1.0,
    "category": "preferences|personal|decisions|behavior"
  }}
]

Only extract meaningful, specific memories. Avoid generic responses.
"""
    
    def _parse_memory_response(self, content: str, user_id: str) -> List[Dict[str, Any]]:
        """Parse LLM response into memory data"""
        try:
            # Try to extract JSON from the response
            content = content.strip()
            
            # Find JSON array in the response
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON array found in response")
            
            json_str = content[start_idx:end_idx]
            memories_data = json.loads(json_str)
            
            # Convert to internal format
            memories = []
            for mem_data in memories_data:
                memory_type = self._parse_memory_type(mem_data.get("memory_type", "factual"))
                
                memories.append({
                    "content": mem_data.get("content", ""),
                    "memory_type": memory_type,
                    "metadata": {
                        "category": mem_data.get("category", "general"),
                        "importance_score": mem_data.get("importance", 1.0),
                        "inferred": True,
                        "source": "ai_inference",
                        "inference_model": self.inference_model,
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
            return memories
            
        except Exception as e:
            print(f"Failed to parse memory response: {e}")
            # Return a single episodic memory as fallback
            return [{
                "content": f"Conversation summary: {content[:200]}...",
                "memory_type": MemoryType.EPISODIC,
                "metadata": {
                    "category": "conversation",
                    "inferred": False,
                    "source": "fallback_parsing",
                    "timestamp": datetime.now().isoformat()
                }
            }]
    
    def _parse_memory_type(self, type_str: str) -> MemoryType:
        """Parse memory type string to MemoryType enum"""
        type_mapping = {
            "factual": MemoryType.FACTUAL,
            "episodic": MemoryType.EPISODIC,
            "semantic": MemoryType.SEMANTIC,
            "working": MemoryType.WORKING
        }
        return type_mapping.get(type_str.lower(), MemoryType.FACTUAL)