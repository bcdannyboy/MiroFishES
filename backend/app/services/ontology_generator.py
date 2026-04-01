"""
Ontology generation service.
Endpoint 1: analyze text content and generate entity and relationship type
definitions suitable for social simulation.
"""

import json
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from .forecast_graph import ensure_layered_ontology


# System prompt for ontology generation
ONTOLOGY_SYSTEM_PROMPT = """You are an expert knowledge-graph ontology designer. Your task is to analyze the provided text content and simulation requirements, then design entity types and relationship types suitable for **social media public-opinion simulation**.

**Important: you must output valid JSON only. Do not output anything else.**

## Core task background

We are building a **social media public-opinion simulation system**. In this system:
- Every entity is an "account" or "actor" that can speak, interact, and spread information on social media
- Entities can influence, repost, comment on, and respond to one another
- We need to simulate how different parties react to opinion-driven events and how information spreads

Therefore, **the graph must include both actors and forecast-native analytical objects**:

**Actor layer**:
- `Person`
- `Organization`

**Analytical layer**:
- `Event`
- `Claim`
- `Evidence`
- `Topic`
- `Metric`
- `TimeWindow`
- `Scenario`
- `UncertaintyFactor`

Actors should represent the people or institutions making statements or influencing outcomes.
Analytical objects should represent the developments, assertions, evidence, topics, metrics, windows, scenarios, and risks that later forecast retrieval and simulation phases need.

## Output format

Output JSON using the following structure:

```json
{
    "entity_types": [
        {
            "name": "Entity type name (English, PascalCase)",
            "description": "Short description (English, max 100 characters)",
            "attributes": [
                {
                    "name": "Attribute name (English, snake_case)",
                    "type": "text",
                    "description": "Attribute description"
                }
            ],
            "examples": ["Example entity 1", "Example entity 2"]
        }
    ],
    "edge_types": [
        {
            "name": "Relationship type name (English, UPPER_SNAKE_CASE)",
            "description": "Short description (English, max 100 characters)",
            "source_targets": [
                {"source": "Source entity type", "target": "Target entity type"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "Brief English analysis of the text content"
}
```

## Design guidelines (very important)

### 1. Entity type design - must be followed strictly

**Quantity requirement: exactly 10 entity types**

Your 10 entity types must be the layered forecast schema:
- `Event`
- `Claim`
- `Evidence`
- `Topic`
- `Metric`
- `TimeWindow`
- `Scenario`
- `UncertaintyFactor`
- `Person`
- `Organization`

Use attributes and examples to adapt these types to the uploaded material.

### 2. Relationship type design

- Quantity: 6-10
- Relationships should connect actors and analytical objects in a forecast-relevant way
- Make sure `source_targets` covers the entity types you define

### 3. Attribute design

- Each entity type should have 1-3 key attributes
- **Note**: attribute names cannot use `name`, `uuid`, `group_id`, `created_at`, or `summary` because those are reserved words
- Recommended options include `full_name`, `title`, `role`, `position`, `location`, and `description`

## Relationship type references

- INVOLVES_ACTOR: event, claim, or scenario involves an actor
- MAKES_CLAIM: actor makes a claim
- SUPPORTED_BY: claim, scenario, or metric is supported by evidence
- REFERS_TO_EVENT: claim, evidence, or scenario refers to an event
- ABOUT_TOPIC: analytical object is about a topic
- MEASURES: metric measures an event, scenario, or topic
- OCCURS_DURING: analytical object occurs during a time window
- HAS_UNCERTAINTY: analytical object has an uncertainty factor
- INFORMS_SCENARIO: analytical object informs a scenario
"""


class OntologyGenerator:
    """
    Ontology generator.
    Analyzes text content and generates entity and relationship definitions.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate the ontology definition.

        Args:
            document_texts: List of document texts
            simulation_requirement: Simulation requirement description
            additional_context: Additional context

        Returns:
            Ontology definition with fields such as `entity_types` and `edge_types`
        """
        # Build the user message.
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        # Call the LLM.
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )
        
        # Validate and post-process the result.
        result = self._validate_and_process(result)
        
        return result
    
    # Maximum text length sent to the LLM (50,000 characters).
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    _PASCAL_CASE_PATTERN = re.compile(r'^[A-Z][A-Za-z0-9]*$')
    _NON_ALNUM_PATTERN = re.compile(r'[^A-Za-z0-9]+')
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """Build the user message."""
        
        # Combine the input texts.
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # Truncate text beyond 50,000 characters for the LLM only.
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += (
                f"\n\n...(original text length: {original_length} characters; "
                f"only the first {self.MAX_TEXT_LENGTH_FOR_LLM} characters were used for ontology analysis)..."
            )

        message = f"""## Simulation Requirement

{simulation_requirement}

## Document Content

{combined_text}
"""
        
        if additional_context:
            message += f"""
## Additional Notes

{additional_context}
"""

        message += """
Based on the information above, design a layered forecast graph ontology.

**Rules that must be followed**:
1. Output exactly 10 entity types
2. Include the layered forecast-native objects Event, Claim, Evidence, Topic, Metric, TimeWindow, Scenario, and UncertaintyFactor
3. Include the actor types Person and Organization
4. Prefer relationships that connect actors to analytical objects and analytical objects to one another
5. Attribute names cannot use reserved words such as `name`, `uuid`, or `group_id`; use names like `full_name` or `org_name` instead
"""
        
        return message

    @classmethod
    def _normalize_lookup_key(cls, value: Any) -> str:
        """Collapse an entity label into a lookup key for loose matching."""
        return cls._NON_ALNUM_PATTERN.sub('', str(value or '')).lower()

    @classmethod
    def _normalize_entity_name(cls, value: Any, fallback: str) -> str:
        """Convert an entity name to the PascalCase format required by Zep."""
        text = str(value or '').strip()
        if cls._PASCAL_CASE_PATTERN.fullmatch(text):
            return text

        parts = [part for part in cls._NON_ALNUM_PATTERN.split(text) if part]
        if not parts:
            compact = cls._NON_ALNUM_PATTERN.sub('', text)
            parts = [compact] if compact else []

        normalized_parts = []
        for part in parts:
            if part.isupper():
                normalized_parts.append(part)
            else:
                normalized_parts.append(part[0].upper() + part[1:])

        candidate = ''.join(normalized_parts) or fallback
        if not candidate:
            return fallback
        if not candidate[0].isalpha():
            candidate = f"Entity{candidate}"

        if cls._PASCAL_CASE_PATTERN.fullmatch(candidate):
            return candidate

        compact = re.sub(r'[^A-Za-z0-9]', '', candidate)
        if not compact:
            return fallback
        if not compact[0].isalpha():
            compact = f"Entity{compact}"
        return compact[0].upper() + compact[1:]

    @classmethod
    def _normalize_entity_types(
        cls,
        entity_types: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Normalize entity names and keep them unique."""
        normalized_entities = []
        used_names = set()

        for index, entity in enumerate(entity_types, start=1):
            normalized_entity = dict(entity)
            base_name = cls._normalize_entity_name(
                normalized_entity.get("name"),
                fallback=f"EntityType{index}"
            )

            name = base_name
            suffix = 2
            while name in used_names:
                name = f"{base_name}{suffix}"
                suffix += 1

            normalized_entity["name"] = name
            normalized_entities.append(normalized_entity)
            used_names.add(name)

        return normalized_entities

    @classmethod
    def _build_entity_lookup(
        cls,
        entity_types: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Build a tolerant lookup from any alias to the canonical entity name."""
        lookup: Dict[str, str] = {}
        for entity in entity_types:
            name = entity.get("name", "")
            key = cls._normalize_lookup_key(name)
            if key:
                lookup[key] = name
        return lookup

    @classmethod
    def _resolve_entity_reference(
        cls,
        value: Any,
        entity_lookup: Dict[str, str]
    ) -> Optional[str]:
        """Resolve an entity reference to a normalized defined entity type."""
        raw_key = cls._normalize_lookup_key(value)
        if raw_key in entity_lookup:
            return entity_lookup[raw_key]

        normalized = cls._normalize_entity_name(value, fallback="")
        normalized_key = cls._normalize_lookup_key(normalized)
        resolved = entity_lookup.get(normalized_key)
        if resolved:
            return resolved

        fallback_value = str(value or "").lower()
        person_markers = {
            "person",
            "student",
            "professor",
            "journalist",
            "celebrity",
            "executive",
            "official",
            "lawyer",
            "doctor",
            "worker",
            "employee",
            "analyst",
            "investor",
            "founder",
            "citizen",
        }
        if "Person" in entity_lookup.values() and any(
            marker in fallback_value for marker in person_markers
        ):
            return "Person"
        if "Organization" in entity_lookup.values():
            return "Organization"
        return None
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and post-process the result."""
        
        # Ensure required fields exist.
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""

        result["entity_types"] = self._normalize_entity_types(result["entity_types"])
        
        # Validate entity types.
        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # Keep descriptions within 100 characters.
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # Validate relationship types.
        for edge in result["edge_types"]:
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        result = ensure_layered_ontology(result)

        # Zep API limits: at most 10 custom entity types and 10 custom edge types.
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        entity_lookup = self._build_entity_lookup(result["entity_types"])

        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]

        valid_entity_names = {entity["name"] for entity in result["entity_types"]}
        for edge in result["edge_types"]:
            normalized_source_targets = []
            for source_target in edge["source_targets"]:
                source = self._resolve_entity_reference(
                    source_target.get("source"),
                    entity_lookup
                )
                target = self._resolve_entity_reference(
                    source_target.get("target"),
                    entity_lookup
                )

                if source in valid_entity_names and target in valid_entity_names:
                    normalized_source_targets.append({
                        "source": source,
                        "target": target
                    })

            edge["source_targets"] = normalized_source_targets
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        Convert the ontology definition to Python code, similar to `ontology.py`.

        Args:
            ontology: Ontology definition

        Returns:
            Python code as a string
        """
        code_lines = [
            '"""',
            'Custom entity type definitions',
            'Automatically generated by MiroFishES for social opinion simulation',
            '"""',
            '',
            'from pydantic import BaseModel, Field',
            '',
            'EntityText = str',
            'EntityModel = BaseModel',
            'EdgeModel = BaseModel',
            '',
            '# ============== Entity Type Definitions ==============',
            '',
        ]
        
        # Generate entity types.
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== Relationship Type Definitions ==============')
        code_lines.append('')
        
        # Generate relationship types.
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # Convert to a PascalCase class name.
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # Generate type dictionaries.
        code_lines.append('# ============== Type Configuration ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # Generate the edge `source_targets` mapping.
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)
