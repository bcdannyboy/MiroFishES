"""
Zep retrieval tool service.

Wraps graph search, node reads, and edge queries for the Report Agent.

Core retrieval tools:
1. InsightForge (deep insight retrieval) - the strongest hybrid retrieval flow,
   automatically generating subquestions and searching across multiple dimensions
2. PanoramaSearch (breadth search) - captures the full picture, including expired content
3. QuickSearch (simple search) - lightweight fast retrieval
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from .graph_backend.query_service import GraphQueryService
from .hybrid_evidence_retriever import HybridEvidenceRetriever

logger = get_logger('mirofish.zep_tools')


@dataclass
class SearchResult:
    """Search result."""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }
    
    def to_text(self) -> str:
        """Render as text for LLM consumption."""
        text_parts = [f"Search query: {self.query}", f"Found {self.total_count} relevant items"]
        
        if self.facts:
            text_parts.append("\n### Related Facts:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """Node information."""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }
    
    def to_text(self) -> str:
        """Render as text."""
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), "Unknown type")
        return f"Entity: {self.name} (Type: {entity_type})\nSummary: {self.summary}"


@dataclass
class EdgeInfo:
    """Edge information."""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = None
    target_node_name: Optional[str] = None
    # Temporal information
    created_at: Optional[str] = None
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    expired_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }
    
    def to_text(self, include_temporal: bool = False) -> str:
        """Render as text."""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"Relationship: {source} --[{self.name}]--> {target}\nFact: {self.fact}"
        
        if include_temporal:
            valid_at = self.valid_at or "Unknown"
            invalid_at = self.invalid_at or "Present"
            base_text += f"\nValidity: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (Expired: {self.expired_at})"
        
        return base_text
    
    @property
    def is_expired(self) -> bool:
        """Whether the edge has expired."""
        return self.expired_at is not None
    
    @property
    def is_invalid(self) -> bool:
        """Whether the edge is invalid."""
        return self.invalid_at is not None


@dataclass
class InsightForgeResult:
    """
    Deep insight retrieval result (InsightForge).

    Contains results for multiple subquestions plus the synthesized analysis.
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    
    # Retrieval results across different dimensions
    semantic_facts: List[str] = field(default_factory=list)  # Semantic search results
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)  # Entity insights
    relationship_chains: List[str] = field(default_factory=list)  # Relationship chains
    
    # Statistics
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }
    
    def to_text(self) -> str:
        """Render as detailed text for LLM consumption."""
        text_parts = [
            "## Deep Forecast Analysis",
            f"Analysis Question: {self.query}",
            f"Forecast Scenario: {self.simulation_requirement}",
            "\n### Forecast Data Statistics",
            f"- Related Forecast Facts: {self.total_facts}",
            f"- Entities Involved: {self.total_entities}",
            f"- Relationship Chains: {self.total_relationships}"
        ]
        
        # Subquestions
        if self.sub_queries:
            text_parts.append("\n### Analyzed Subquestions")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")
        
        # Semantic search results
        if self.semantic_facts:
            text_parts.append("\n### [Key Facts] (Please cite these original lines in the report)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Entity insights
        if self.entity_insights:
            text_parts.append("\n### [Core Entities]")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', 'Unknown')}** ({entity.get('type', 'Entity')})")
                if entity.get('summary'):
                    text_parts.append(f"  Summary: \"{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f"  Related facts: {len(entity.get('related_facts', []))}")
        
        # Relationship chains
        if self.relationship_chains:
            text_parts.append("\n### [Relationship Chains]")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")
        
        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    Breadth search result (Panorama).

    Includes all related information, including expired content.
    """
    query: str
    
    # All nodes
    all_nodes: List[NodeInfo] = field(default_factory=list)
    # All edges, including expired ones
    all_edges: List[EdgeInfo] = field(default_factory=list)
    # Currently valid facts
    active_facts: List[str] = field(default_factory=list)
    # Expired or invalid facts (history)
    historical_facts: List[str] = field(default_factory=list)
    
    # Statistics
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }
    
    def to_text(self) -> str:
        """Render as text in full form without truncation."""
        text_parts = [
            "## Panorama Search Results (Future Panorama View)",
            f"Query: {self.query}",
            "\n### Statistics",
            f"- Total Nodes: {self.total_nodes}",
            f"- Total Edges: {self.total_edges}",
            f"- Current Valid Facts: {self.active_count}",
            f"- Historical/Expired Facts: {self.historical_count}"
        ]
        
        # Current valid facts, emitted in full without truncation
        if self.active_facts:
            text_parts.append("\n### [Current Valid Facts] (Original simulation output)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Historical or expired facts, emitted in full without truncation
        if self.historical_facts:
            text_parts.append("\n### [Historical/Expired Facts] (Evolution history)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Key entities, emitted in full without truncation
        if self.all_nodes:
            text_parts.append("\n### [Entities Involved]")
            for node in self.all_nodes:
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entity")
                text_parts.append(f"- **{node.name}** ({entity_type})")
        
        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """Interview result for a single agent."""
    agent_name: str
    agent_role: str  # Role type, such as student, teacher, or media
    agent_bio: str  # Short bio
    question: str  # Interview question
    response: str  # Interview answer
    key_quotes: List[str] = field(default_factory=list)  # Key quotes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }
    
    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        # Show the full agent_bio without truncation.
        text += f"_Bio: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**Key Quotes:**\n"
            for quote in self.key_quotes:
                # Normalize quote characters.
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                # Strip leading punctuation.
                while clean_quote and clean_quote[0] in '\uFF0C,\uFF1B;\uFF1A:\u3001\u3002\uFF01\uFF1F\n\r\t ':
                    clean_quote = clean_quote[1:]
                # Drop junk text that includes question numbering (Question 1-9).
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                # Trim overly long content at sentence boundaries instead of hard cutoff.
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    Interview result.

    Contains interview responses from multiple simulated agents.
    """
    interview_topic: str  # Interview topic
    interview_questions: List[str]  # Interview question list
    
    # Agents selected for the interview
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    # Interview answers for each agent
    interviews: List[AgentInterview] = field(default_factory=list)
    
    # Why these agents were selected
    selection_reasoning: str = ""
    # Synthesized summary of the interview
    summary: str = ""
    
    # Statistics
    total_agents: int = 0
    interviewed_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }
    
    def to_text(self) -> str:
        """Render as detailed text for LLM consumption and report citation."""
        text_parts = [
            "## In-Depth Interview Report",
            f"**Interview Topic:** {self.interview_topic}",
            f"**Interviewed Agents:** {self.interviewed_count} / {self.total_agents} simulated agents",
            "\n### Why These Agents Were Selected",
            self.selection_reasoning or "(Automatically selected)",
            "\n---",
            "\n### Interview Transcript",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### Interview #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("(No interview records)\n\n---")

        text_parts.append("\n### Interview Summary and Core Viewpoints")
        text_parts.append(self.summary or "(No summary)")

        return "\n".join(text_parts)


@dataclass
class HybridEvidenceSearchResult:
    """Hybrid local evidence retrieval result for cited report consumption."""

    query: str
    project_id: str
    entries: List[Dict[str, Any]] = field(default_factory=list)
    missing_evidence_markers: List[Dict[str, Any]] = field(default_factory=list)
    index_stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_count(self) -> int:
        return len(self.entries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "project_id": self.project_id,
            "entries": self.entries,
            "missing_evidence_markers": self.missing_evidence_markers,
            "index_stats": self.index_stats,
            "total_count": self.total_count,
        }

    def to_text(self) -> str:
        text_parts = [
            "## Hybrid Evidence Search",
            f"Query: {self.query}",
            f"Project: {self.project_id}",
            f"Retrieved evidence items: {self.total_count}",
        ]
        for index, entry in enumerate(self.entries, start=1):
            object_type = entry.get("object_type") or entry.get("record_type") or "evidence"
            text_parts.append(
                f"{index}. {entry.get('title', 'Evidence')} ({object_type}, {entry.get('conflict_status', 'none')})"
            )
            if entry.get("summary"):
                text_parts.append(f"   Summary: {entry['summary']}")
            citations = [item.get("citation_id") for item in entry.get("citations", []) if item.get("citation_id")]
            if citations:
                text_parts.append(f"   Citations: {', '.join(citations)}")
        for marker in self.missing_evidence_markers:
            reason = marker.get("reason") or marker.get("summary")
            if reason:
                text_parts.append(f"- Missing evidence: {reason}")
        return "\n".join(text_parts)


class ZepToolsService:
    """
    Zep retrieval tool service.

    Core retrieval tools:
    1. `insight_forge` - deep insight retrieval with automatic subquestion generation
    2. `panorama_search` - breadth search for the full picture, including expired content
    3. `quick_search` - lightweight fast retrieval
    4. `interview_agents` - in-depth interviews with simulated agents for multi-perspective viewpoints

    Base tools:
    - `search_graph` - semantic graph search
    - `get_all_nodes` - fetch all graph nodes
    - `get_all_edges` - fetch all graph edges with temporal metadata
    - `get_node_detail` - fetch a single node in detail
    - `get_node_edges` - fetch edges related to one node
    - `get_entities_by_type` - fetch entities by type
    - `get_entity_summary` - fetch a relation summary for one entity
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        hybrid_evidence_retriever: Optional[HybridEvidenceRetriever] = None,
        query_service: Optional[GraphQueryService] = None,
    ):
        self.api_key = api_key or Config.ZEP_API_KEY or ""
        self._llm_client = llm_client
        self.hybrid_evidence_retriever = hybrid_evidence_retriever
        self.query_service = query_service or GraphQueryService()
        logger.info("Graph-backed query tools initialized")
    
    @property
    def llm(self) -> LLMClient:
        """Lazily initialize the LLM client."""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    @property
    def hybrid_retriever(self) -> HybridEvidenceRetriever:
        if self.hybrid_evidence_retriever is None:
            self.hybrid_evidence_retriever = HybridEvidenceRetriever()
        return self.hybrid_evidence_retriever

    def _normalize_graph_ids(
        self,
        graph_id: Optional[str] = None,
        graph_ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Support merged retrieval while keeping single-graph callers unchanged."""
        normalized: List[str] = []
        seen = set()
        for candidate in [graph_id, *(graph_ids or [])]:
            if not candidate:
                continue
            candidate_text = str(candidate).strip()
            if not candidate_text or candidate_text in seen:
                continue
            normalized.append(candidate_text)
            seen.add(candidate_text)
        if not normalized:
            raise ValueError("graph_id or graph_ids is required")
        return normalized

    def _merge_search_results(
        self,
        results: List[SearchResult],
        *,
        query: str,
        limit: int,
    ) -> SearchResult:
        """Merge search results deterministically across multiple graphs."""
        facts: List[str] = []
        edges: List[Dict[str, Any]] = []
        nodes: List[Dict[str, Any]] = []
        seen_facts = set()
        seen_edges = set()
        seen_nodes = set()

        for result in results:
            for fact in result.facts:
                if fact in seen_facts:
                    continue
                seen_facts.add(fact)
                facts.append(fact)

            for edge in result.edges:
                edge_key = (
                    edge.get("uuid")
                    or (
                        edge.get("name"),
                        edge.get("fact"),
                        edge.get("source_node_uuid"),
                        edge.get("target_node_uuid"),
                    )
                )
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edges.append(edge)

            for node in result.nodes:
                node_key = (
                    node.get("uuid")
                    or (
                        node.get("name"),
                        tuple(node.get("labels", [])),
                        node.get("summary"),
                    )
                )
                if node_key in seen_nodes:
                    continue
                seen_nodes.add(node_key)
                nodes.append(node)

        merged_facts = facts[:limit]
        merged_edges = edges[:limit]
        merged_nodes = nodes[:limit]
        return SearchResult(
            facts=merged_facts,
            edges=merged_edges,
            nodes=merged_nodes,
            query=query,
            total_count=len(merged_facts),
        )
    
    def search_graph(
        self, 
        graph_id: Optional[str], 
        query: str, 
        limit: int = 10,
        scope: str = "edges",
        graph_ids: Optional[List[str]] = None,
    ) -> SearchResult:
        """
        Semantic graph search.

        Uses hybrid search (semantic + BM25) to search for related graph content.
        Falls back to local keyword matching if the Zep Cloud search API is unavailable.
        
        Args:
            graph_id: Graph ID (Standalone Graph)
            query: Search query
            limit: Number of results to return
            scope: Search scope, `"edges"` or `"nodes"`
            
        Returns:
            SearchResult: Search results
        """
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        if len(normalized_graph_ids) > 1:
            logger.info(
                "Merged graph search: graph_ids=%s, query=%s...",
                normalized_graph_ids,
                query[:50],
            )
            return self._merge_search_results(
                [
                    self._search_single_graph(current_graph_id, query, limit, scope)
                    for current_graph_id in normalized_graph_ids
                ],
                query=query,
                limit=limit,
            )
        return self._search_single_graph(
            normalized_graph_ids[0],
            query,
            limit,
            scope,
        )

    def _search_single_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges",
    ) -> SearchResult:
        """Run graph search against one concrete graph."""
        logger.info("Artifact-backed graph search: graph_id=%s query=%s", graph_id, query[:50])
        search_result = self.query_service.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope=scope,
        )
        return SearchResult(
            facts=list(search_result["facts"]),
            edges=list(search_result["edges"]),
            nodes=list(search_result["nodes"]),
            query=query,
            total_count=int(search_result["total_count"]),
        )
    
    def get_all_nodes(
        self,
        graph_id: Optional[str],
        graph_ids: Optional[List[str]] = None,
    ) -> List[NodeInfo]:
        """
        Fetch all graph nodes with pagination.

        Args:
            graph_id: Graph ID

        Returns:
            Node list
        """
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        nodes = self.query_service.get_all_nodes(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
        )
        return [
            NodeInfo(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=list(node.get("labels", [])),
                summary=node.get("summary", ""),
                attributes=dict(node.get("attributes", {})),
            )
            for node in nodes
        ]

    def get_all_edges(
        self,
        graph_id: Optional[str],
        include_temporal: bool = True,
        graph_ids: Optional[List[str]] = None,
    ) -> List[EdgeInfo]:
        """
        Fetch all graph edges with pagination and temporal data.

        Args:
            graph_id: Graph ID
            include_temporal: Whether to include temporal information (default: True)

        Returns:
            Edge list including `created_at`, `valid_at`, `invalid_at`, and `expired_at`
        """
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        edges = self.query_service.get_all_edges(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
        )
        result: List[EdgeInfo] = []
        for edge in edges:
            edge_info = EdgeInfo(
                uuid=edge.get("uuid", ""),
                name=edge.get("name", ""),
                fact=edge.get("fact", ""),
                source_node_uuid=edge.get("source_node_uuid", ""),
                target_node_uuid=edge.get("target_node_uuid", ""),
                source_node_name=edge.get("source_node_name") or None,
                target_node_name=edge.get("target_node_name") or None,
            )
            if include_temporal:
                edge_info.created_at = edge.get("created_at")
                edge_info.valid_at = edge.get("valid_at")
                edge_info.invalid_at = edge.get("invalid_at")
                edge_info.expired_at = edge.get("expired_at")
            result.append(edge_info)
        return result
    
    def get_node_detail(
        self,
        node_uuid: str,
        graph_id: Optional[str] = None,
        graph_ids: Optional[List[str]] = None,
    ) -> Optional[NodeInfo]:
        """
        Fetch detailed information for a single node.
        
        Args:
            node_uuid: Node UUID
            
        Returns:
            Node information or `None`
        """
        if graph_id is None and not graph_ids:
            return None
        normalized_graph_ids = self._normalize_graph_ids(
            graph_id,
            graph_ids,
        )
        node = self.query_service.get_node_detail(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            node_uuid=node_uuid,
        )
        if not node:
            return None
        return NodeInfo(
            uuid=node.get("uuid", ""),
            name=node.get("name", ""),
            labels=list(node.get("labels", [])),
            summary=node.get("summary", ""),
            attributes=dict(node.get("attributes", {})),
        )
    
    def get_node_edges(
        self,
        graph_id: Optional[str],
        node_uuid: str,
        graph_ids: Optional[List[str]] = None,
    ) -> List[EdgeInfo]:
        """
        Fetch all edges related to a node.

        This is implemented by fetching all graph edges and filtering for the target node.
        
        Args:
            graph_id: Graph ID
            node_uuid: Node UUID
            
        Returns:
            Edge list
        """
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        edges = self.query_service.get_node_edges(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            node_uuid=node_uuid,
        )
        return [
            EdgeInfo(
                uuid=edge.get("uuid", ""),
                name=edge.get("name", ""),
                fact=edge.get("fact", ""),
                source_node_uuid=edge.get("source_node_uuid", ""),
                target_node_uuid=edge.get("target_node_uuid", ""),
                source_node_name=edge.get("source_node_name") or None,
                target_node_name=edge.get("target_node_name") or None,
                created_at=edge.get("created_at"),
                valid_at=edge.get("valid_at"),
                invalid_at=edge.get("invalid_at"),
                expired_at=edge.get("expired_at"),
            )
            for edge in edges
        ]
    
    def get_entities_by_type(
        self, 
        graph_id: Optional[str], 
        entity_type: str,
        graph_ids: Optional[List[str]] = None,
    ) -> List[NodeInfo]:
        """
        Fetch entities by type.
        
        Args:
            graph_id: Graph ID
            entity_type: Entity type, such as `Student` or `PublicFigure`
            
        Returns:
            Matching entities
        """
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        return [
            NodeInfo(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=list(node.get("labels", [])),
                summary=node.get("summary", ""),
                attributes=dict(node.get("attributes", {})),
            )
            for node in self.query_service.get_entities_by_type(
                graph_id=normalized_graph_ids[0],
                graph_ids=normalized_graph_ids,
                entity_type=entity_type,
            )
        ]
    
    def get_entity_summary(
        self, 
        graph_id: Optional[str], 
        entity_name: str,
        graph_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a relationship summary for a specific entity.

        Searches all information related to the entity and returns a summary.
        
        Args:
            graph_id: Graph ID
            entity_name: Entity name
            
        Returns:
            Entity summary information
        """
        logger.info(f"Fetching relationship summary for entity {entity_name}...")
        
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        return self.query_service.get_entity_summary(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            entity_name=entity_name,
        )
    
    def get_graph_statistics(
        self,
        graph_id: Optional[str],
        graph_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch graph statistics.
        
        Args:
            graph_id: Graph ID
            
        Returns:
            Statistics
        """
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        return self.query_service.get_graph_statistics(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
        )
    
    def get_simulation_context(
        self, 
        graph_id: Optional[str],
        simulation_requirement: str,
        limit: int = 30,
        graph_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch simulation-relevant context.

        Aggregates all information related to the simulation requirement.
        
        Args:
            graph_id: Graph ID
            simulation_requirement: Simulation requirement description
            limit: Maximum item count per category
            
        Returns:
            Simulation context information
        """
        logger.info(f"Fetching simulation context: {simulation_requirement[:50]}...")
        
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        return self.query_service.get_simulation_context(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            simulation_requirement=simulation_requirement,
            limit=limit,
        )
    
    # ========== Core retrieval tools ==========
    
    def insight_forge(
        self,
        graph_id: Optional[str],
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5,
        graph_ids: Optional[List[str]] = None,
    ) -> InsightForgeResult:
        """
        InsightForge - deep insight retrieval.

        The most powerful hybrid retrieval flow. It automatically decomposes the
        question and retrieves across multiple dimensions:
        1. Uses the LLM to break the question into subquestions
        2. Runs semantic search for each subquestion
        3. Extracts related entities and fetches their details
        4. Builds relationship chains
        5. Synthesizes everything into deep insight
        
        Args:
            graph_id: Graph ID
            query: User question
            simulation_requirement: Simulation requirement description
            report_context: Report context, optional, used to generate better subquestions
            max_sub_queries: Maximum number of subquestions
            
        Returns:
            InsightForgeResult: Deep insight retrieval result
        """
        logger.info(f"InsightForge deep insight retrieval: {query[:50]}...")
        
        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        
        # Step 1: Use the LLM to generate subquestions.
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(f"Generated {len(sub_queries)} subquestions")
        
        # Step 2: Run semantic search for each subquestion.
        all_facts = []
        all_edges = []
        seen_facts = set()
        
        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=normalized_graph_ids[0],
                graph_ids=normalized_graph_ids,
                query=sub_query,
                limit=15,
                scope="edges"
            )
            
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            
            all_edges.extend(search_result.edges)
        
        # Also search for the original question directly.
        main_search = self.search_graph(
            graph_id=normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)
        
        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)
        
        # Step 3: Extract related entity UUIDs from edges and fetch only those entities.
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)
        
        # Fetch every related entity without truncation.
        entity_insights = []
        node_map = {}  # Used later to build relationship chains.
        
        for uuid in list(entity_uuids):  # Process all entities without truncation.
            if not uuid:
                continue
            try:
                # Fetch each related node individually.
                node = self.get_node_detail(
                    uuid,
                    graph_id=normalized_graph_ids[0],
                    graph_ids=normalized_graph_ids,
                )
                if node:
                    node_map[uuid] = node
                    entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entity")
                    
                    # Collect all related facts for this entity without truncation.
                    related_facts = [
                        f for f in all_facts 
                        if node.name.lower() in f.lower()
                    ]
                    
                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts  # Full output, no truncation.
                    })
            except Exception as e:
                logger.debug(f"Failed to fetch node {uuid}: {e}")
                continue
        
        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)
        
        # Step 4: Build every relationship chain without truncation.
        relationship_chains = []
        for edge_data in all_edges:  # Process all edges without truncation.
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')
                
                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]
                
                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)
        
        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)
        
        logger.info(
            f"InsightForge completed: {result.total_facts} facts, "
            f"{result.total_entities} entities, {result.total_relationships} relationships"
        )
        return result
    
    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """
        Generate subquestions with the LLM.

        Breaks a complex question into smaller, independently retrievable subquestions.
        """
        system_prompt = """You are an expert problem analyst. Your task is to break a complex question into multiple subquestions that can be observed independently in the simulated world.

Requirements:
1. Each subquestion must be specific enough to map to agent behavior or events in the simulation.
2. The subquestions should cover different dimensions of the original problem, such as who, what, why, how, when, and where.
3. The subquestions should remain relevant to the simulation scenario.
4. Return JSON in this format: {"sub_queries": ["subquestion 1", "subquestion 2", ...]}"""

        user_prompt = f"""Simulation requirement background:
{simulation_requirement}

{f"Report context: {report_context[:500]}" if report_context else ""}

Please decompose the following question into {max_queries} subquestions:
{query}

Return the subquestion list as JSON."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            sub_queries = response.get("sub_queries", [])
            # Ensure the result is a list of strings.
            return [str(sq) for sq in sub_queries[:max_queries]]
            
        except Exception as e:
            logger.warning(f"Failed to generate subquestions: {str(e)}. Using defaults.")
            # Fallback: return simple variations of the original question.
            return [
                query,
                f"Main participants in {query}",
                f"Causes and impacts of {query}",
                f"How {query} develops over time"
            ][:max_queries]
    
    def panorama_search(
        self,
        graph_id: Optional[str],
        query: str,
        include_expired: bool = True,
        limit: int = 50,
        graph_ids: Optional[List[str]] = None,
    ) -> PanoramaResult:
        """
        PanoramaSearch - breadth search.

        Produces a full-picture view, including relevant content plus historical and
        expired information:
        1. Fetch all related nodes
        2. Fetch all edges, including expired or invalid ones
        3. Separate current information from historical information

        This tool is best when you need to understand the whole event and trace how it evolved.
        
        Args:
            graph_id: Graph ID
            query: Search query used for relevance sorting
            include_expired: Whether to include expired content (default: True)
            limit: Maximum number of results to return
            
        Returns:
            PanoramaResult: Panorama search result
        """
        logger.info(f"PanoramaSearch breadth search: {query[:50]}...")
        
        result = PanoramaResult(query=query)
        normalized_graph_ids = self._normalize_graph_ids(graph_id, graph_ids)
        
        all_nodes = self.get_all_nodes(
            normalized_graph_ids[0],
            graph_ids=normalized_graph_ids,
        )
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)
        
        all_edges = self.get_all_edges(
            normalized_graph_ids[0],
            include_temporal=True,
            graph_ids=normalized_graph_ids,
        )
        result.all_edges = all_edges
        result.total_edges = len(all_edges)
        
        # Partition facts by time status.
        active_facts = []
        historical_facts = []
        
        for edge in all_edges:
            if not edge.fact:
                continue
            
            is_historical = (
                edge.is_expired
                or edge.is_invalid
                or bool(edge.attributes.get("history_kind") == "runtime_transition")
            )
            
            if is_historical:
                valid_at = edge.valid_at or "Unknown"
                invalid_at = edge.invalid_at or edge.expired_at or "Unknown"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                active_facts.append(edge.fact)
        
        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)
        
        logger.info(
            f"PanoramaSearch completed: {result.active_count} active facts, "
            f"{result.historical_count} historical facts"
        )
        return result
    
    def quick_search(
        self,
        graph_id: Optional[str],
        query: str,
        limit: int = 10,
        graph_ids: Optional[List[str]] = None,
    ) -> SearchResult:
        """
        QuickSearch - simple search.

        A fast lightweight retrieval tool:
        1. Calls Zep semantic search directly
        2. Returns the most relevant results
        3. Best for simple and direct retrieval needs
        
        Args:
            graph_id: Graph ID
            query: Search query
            limit: Number of results to return
            
        Returns:
            SearchResult: Search results
        """
        logger.info(f"QuickSearch simple search: {query[:50]}...")
        
        # Directly reuse the existing search_graph implementation.
        result = self.search_graph(
            graph_id=graph_id,
            graph_ids=graph_ids,
            query=query,
            limit=limit,
            scope="edges"
        )
        
        logger.info(f"QuickSearch completed: {result.total_count} results")
        return result

    def hybrid_evidence_search(
        self,
        *,
        project_id: str,
        graph_id: Optional[str],
        query: str,
        graph_ids: Optional[List[str]] = None,
        limit: int = 6,
        question_type: str = "binary",
        issue_timestamp: Optional[str] = None,
    ) -> HybridEvidenceSearchResult:
        """Search persisted source units and graph objects with cited hybrid ranking."""
        result = self.hybrid_retriever.retrieve(
            project_id=project_id,
            query=query,
            question_type=question_type,
            issue_timestamp=issue_timestamp,
            limit=limit,
        )
        return HybridEvidenceSearchResult(
            query=query,
            project_id=project_id,
            entries=list(result.hits),
            missing_evidence_markers=list(result.missing_evidence_markers),
            index_stats=dict(result.index_stats),
        )
    
    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """
        InterviewAgents: deep interview flow.

        Calls the real OASIS interview API to interview currently running
        simulation agents:
        1. Load the persona files and inspect the full agent roster.
        2. Use the LLM to select the most relevant agents for the request.
        3. Use the LLM to generate interview questions.
        4. Call `/api/simulation/interview/batch` to run real interviews
           across both platforms.
        5. Aggregate the interview results into an interview report.

        Important: the simulation environment must still be running and
        waiting for commands.

        Typical use cases:
        - Understand how different roles view an event.
        - Collect a range of opinions and perspectives.
        - Retrieve authentic simulated agent responses instead of a single
          synthesized LLM answer.
        
        Args:
            simulation_id: Simulation ID used to locate persona files and call
                the interview API.
            interview_requirement: Unstructured interview goal, for example
                "understand how students view the event".
            simulation_requirement: Optional simulation background context.
            max_agents: Maximum number of agents to interview.
            custom_questions: Optional custom interview questions. If omitted,
                they are generated automatically.
            
        Returns:
            InterviewResult: Interview results.
        """
        from .simulation_runner import SimulationRunner
        
        logger.info(f"InterviewAgents deep interview (real API): {interview_requirement[:50]}...")
        
        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )
        
        # Step 1: Load the persona files.
        profiles = self._load_agent_profiles(simulation_id)
        
        if not profiles:
            logger.warning(f"No persona files found for simulation {simulation_id}")
            result.summary = "No interviewable agent persona files were found."
            return result
        
        result.total_agents = len(profiles)
        logger.info(f"Loaded {len(profiles)} agent personas")
        
        # Step 2: Use the LLM to choose agents to interview.
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )
        
        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(f"Selected {len(selected_agents)} agents for interviews: {selected_indices}")
        
        # Step 3: Generate interview questions when none were supplied.
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(f"Generated {len(result.interview_questions)} interview questions")
        
        # Merge the questions into one interview prompt.
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])
        
        # Add a prefix that constrains the response format.
        INTERVIEW_PROMPT_PREFIX = (
            "You are being interviewed. Use your persona, memories, and prior "
            "actions to answer the following questions directly in plain text.\n"
            "Response requirements:\n"
            "1. Answer in natural language without calling any tools.\n"
            "2. Do not return JSON or tool-call formatting.\n"
            "3. Do not use Markdown headings such as #, ##, or ###.\n"
            "4. Answer each question in order and begin each answer with "
            "\"Question X:\" where X is the question number.\n"
            "5. Separate answers with a blank line.\n"
            "6. Give substantive answers with at least 2-3 sentences per "
            "question.\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"
        
        # Step 4: Call the real interview API in dual-platform mode.
        try:
            # Build the batch interview payload. Leaving platform unset triggers
            # interviews on both platforms.
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt  # Use the optimized prompt.
                    # If platform is omitted, the API interviews both Twitter
                    # and Reddit.
                })
            
            logger.info(f"Calling batch interview API in dual-platform mode for {len(interviews_request)} agents")
            
            # Use SimulationRunner's batch interview helper without a platform
            # so both platforms are queried.
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,  # Omit platform for dual-platform interviewing.
                timeout=180.0   # Dual-platform runs need a longer timeout.
            )
            
            logger.info(
                f"Interview API returned {api_result.get('interviews_count', 0)} "
                f"results, success={api_result.get('success')}"
            )
            
            # Check whether the API call succeeded.
            if not api_result.get("success", False):
                error_msg = api_result.get("error", "Unknown error")
                logger.warning(f"Interview API reported failure: {error_msg}")
                result.summary = (
                    f"Interview API call failed: {error_msg}. "
                    "Check the OASIS simulation environment state."
                )
                return result
            
            # Step 5: Parse the API response and build AgentInterview objects.
            # Dual-platform mode returns a payload like:
            # {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}
            
            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "Unknown")
                agent_bio = agent.get("bio", "")
                
                # Fetch the interview result for this agent on both platforms.
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})
                
                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # Clean any tool-call JSON wrapper from the responses.
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # Always emit both platform sections.
                twitter_text = twitter_response if twitter_response else "(No reply was received on this platform)"
                reddit_text = reddit_response if reddit_response else "(No reply was received on this platform)"
                response_text = f"[Twitter Response]\n{twitter_text}\n\n[Reddit Response]\n{reddit_text}"

                # Extract key quotes from both platform responses.
                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                # Remove labels, numbering, and Markdown noise from the text.
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'Question\s*\d+:\s*', '', clean_text)
                clean_text = re.sub(r'\[[^\]]+\]', '', clean_text)

                # Strategy 1: extract complete, substantive sentences.
                sentences = re.split(r'[.!?]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W,;:]+', s.strip())
                    and not s.strip().startswith(('{', 'Question'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "." for s in meaningful[:3]]

                # Strategy 2: fall back to long quoted spans.
                if not key_quotes:
                    paired = re.findall(r'"([^"\n]{15,100})"', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[,;:]', q)][:3]
                
                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # Allow a longer bio excerpt.
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)
            
            result.interviewed_count = len(result.interviews)
            
        except ValueError as e:
            # The simulation environment is not running.
            logger.warning(f"Interview API call failed (environment not running?): {e}")
            result.summary = (
                f"Interview failed: {str(e)}. "
                "The simulation environment may be closed. Make sure the OASIS "
                "environment is running."
            )
            return result
        except Exception as e:
            logger.error(f"Interview API call raised an exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"An error occurred during the interview process: {str(e)}"
            return result
        
        # Step 6: Generate the interview summary.
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )
        
        logger.info(
            f"InterviewAgents completed: interviewed {result.interviewed_count} "
            f"agents across both platforms"
        )
        return result
    
    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """Strip a JSON tool-call wrapper from an agent response and return the content."""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Load the simulation's agent persona files."""
        import os
        import csv
        
        # Build the persona file directory path.
        sim_dir = os.path.join(
            os.path.dirname(__file__), 
            f'../../uploads/simulations/{simulation_id}'
        )
        
        profiles = []
        
        # Prefer the Reddit JSON format first.
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(f"Loaded {len(profiles)} personas from reddit_profiles.json")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read reddit_profiles.json: {e}")
        
        # Fall back to the Twitter CSV format.
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Convert the CSV row into the shared profile shape.
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "Unknown"
                        })
                logger.info(f"Loaded {len(profiles)} personas from twitter_profiles.csv")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read twitter_profiles.csv: {e}")
        
        return profiles
    
    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
        Use the LLM to choose which agents to interview.
        
        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: Full profile information for the selected agents.
                - selected_indices: Indices of the selected agents, used for API calls.
                - reasoning: Explanation of the selection.
        """
        
        # Build a compact summary list for candidate agents.
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "Unknown"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)
        
        system_prompt = """You are an expert interview producer. Based on the interview goal, choose the most suitable agents from the simulated agent list.

Selection criteria:
1. The agent's identity or role is relevant to the interview topic.
2. The agent is likely to hold a distinctive or valuable perspective.
3. Choose a diverse set of viewpoints, such as supporters, critics, neutral voices, and domain experts.
4. Prioritize roles that are directly involved in the event.

Return JSON in this format:
{
    "selected_indices": [selected_agent_indices],
    "reasoning": "explanation of why these agents were chosen"
}"""

        user_prompt = f"""Interview goal:
{interview_requirement}

Simulation background:
{simulation_requirement if simulation_requirement else "Not provided"}

Available agent list ({len(agent_summaries)} total):
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

Choose up to {max_agents} agents who are the best fit for this interview and explain why."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "Selected automatically based on relevance")
            
            # Retrieve the full profiles for the selected agents.
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)
            
            return selected_agents, valid_indices, reasoning
            
        except Exception as e:
            logger.warning(f"LLM agent selection failed, using the default selection: {e}")
            # Fallback: choose the first N agents.
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "Used the default selection strategy"
    
    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """Use the LLM to generate interview questions."""
        
        agent_roles = [a.get("profession", "Unknown") for a in selected_agents]
        
        system_prompt = """You are a professional reporter and interviewer. Generate 3-5 deep interview questions based on the interview goal.

Question requirements:
1. Use open-ended questions that encourage detailed answers.
2. The questions should allow different roles to provide different answers.
3. Cover facts, opinions, and emotions from multiple angles.
4. Use natural language that feels like a real interview.
5. Keep each question short and clear.
6. Ask the question directly without adding background explanation or prefixes.

Return JSON in this format: {"questions": ["Question 1", "Question 2", ...]}"""

        user_prompt = f"""Interview goal: {interview_requirement}

Simulation background: {simulation_requirement if simulation_requirement else "Not provided"}

Interview subject roles: {', '.join(agent_roles)}

Generate 3-5 interview questions."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )
            
            return response.get("questions", [f"What is your view on {interview_requirement}?"])
            
        except Exception as e:
            logger.warning(f"Failed to generate interview questions: {e}")
            return [
                f"What is your perspective on {interview_requirement}?",
                "How does this situation affect you or the group you represent?",
                "How do you think this issue should be resolved or improved?"
            ]
    
    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """Generate the interview summary."""
        
        if not interviews:
            return "No interviews were completed."
        
        # Gather the interview contents.
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"[{interview.agent_name} ({interview.agent_role})]\n{interview.response[:500]}")
        
        system_prompt = """You are a professional news editor. Based on the interview responses, generate a concise interview summary.

Summary requirements:
1. Distill the major viewpoints from each side.
2. Point out areas of agreement and disagreement.
3. Highlight valuable quotes.
4. Remain objective and neutral.
5. Keep the summary reasonably concise.

Formatting constraints:
- Use plain-text paragraphs separated by blank lines.
- Do not use Markdown headings such as #, ##, or ###.
- Do not use divider lines such as --- or ***.
- Use standard double quotes for direct quotes.
- You may use **bold** for key terms, but avoid other Markdown syntax."""

        user_prompt = f"""Interview topic: {interview_requirement}

Interview content:
{"".join(interview_texts)}

Generate the interview summary."""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary
            
        except Exception as e:
            logger.warning(f"Failed to generate the interview summary: {e}")
            # Fallback: simple concatenation.
            return (
                f"Interviewed {len(interviews)} respondents, including: "
                + ", ".join([i.agent_name for i in interviews])
            )
