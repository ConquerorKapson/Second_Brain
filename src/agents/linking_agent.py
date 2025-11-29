"""
LinkingAgent skeleton.

Responsibilities:
 - suggest semantic links between nodes
 - create candidate edges with confidence scores
 - optionally call human-in-the-loop approval
"""
from typing import List, Dict

class LinkingAgent:
    def __init__(self):
        pass

    async def find_links(self, nodes: List[Dict]) -> List[Dict]:
        # return list of edges: {source, target, relation, score}
        return []
