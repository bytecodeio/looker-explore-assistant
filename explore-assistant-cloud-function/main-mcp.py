import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'explore-assistant-vector-mcp'))

from server import VectorMCPServer
import asyncio

class EnhancedMCPServer:
    def __init__(self):
        self.vector_server = VectorMCPServer()
        # ...existing code...
    
    async def determine_explore_from_prompt(self, prompt: str, available_explores: List[str]) -> str:
        """Enhanced explore selection using vector similarity"""
        try:
            # Use vector search for semantic matching
            vector_results = await self.vector_server.search_explores(prompt, top_k=5)
            
            # Filter by available explores
            matching_explores = []
            for result in vector_results:
                explore_key = f"{result['model']}:{result['explore']}"
                if explore_key in available_explores:
                    matching_explores.append({
                        'explore_key': explore_key,
                        'similarity': result['similarity'],
                        'reason': result.get('description', '')
                    })
            
            if matching_explores:
                best_match = matching_explores[0]
                print(f"Vector-selected explore: {best_match['explore_key']} (similarity: {best_match['similarity']:.3f})")
                return best_match['explore_key']
                
        except Exception as e:
            print(f"Vector search failed, falling back to keyword matching: {e}")
            
        # Fallback to existing keyword matching
        return self._legacy_determine_explore_from_prompt(prompt, available_explores)
    
    def _legacy_determine_explore_from_prompt(self, prompt: str, available_explores: List[str]) -> str:
        """Original keyword-based explore selection"""
        # ...existing implementation...
        pass

    async def get_relevant_examples(self, explore_key: str, prompt: str, limit: int = 5) -> List[Dict]:
        """Get semantically relevant golden query examples"""
        try:
            examples = await self.vector_server.search_examples(
                explore_key=explore_key,
                query=prompt,
                top_k=limit
            )
            return examples
        except Exception as e:
            print(f"Vector example search failed: {e}")
            return self._get_legacy_examples(explore_key, limit)
    
    def _get_legacy_examples(self, explore_key: str, limit: int) -> List[Dict]:
        """Fallback to loading all examples"""
        # ...existing implementation...
        pass