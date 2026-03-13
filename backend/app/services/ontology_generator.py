"""
Ontology generation service.
Endpoint 1: analyze text content and generate entity and relationship type
definitions suitable for social simulation.
"""

import json
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient


# System prompt for ontology generation
ONTOLOGY_SYSTEM_PROMPT = """You are an expert knowledge-graph ontology designer. Your task is to analyze the provided text content and simulation requirements, then design entity types and relationship types suitable for **social media public-opinion simulation**.

**Important: you must output valid JSON only. Do not output anything else.**

## Core task background

We are building a **social media public-opinion simulation system**. In this system:
- Every entity is an "account" or "actor" that can speak, interact, and spread information on social media
- Entities can influence, repost, comment on, and respond to one another
- We need to simulate how different parties react to opinion-driven events and how information spreads

Therefore, **entities must be real-world actors that can speak and interact on social media**:

**Allowed**:
- Specific individuals such as public figures, involved parties, opinion leaders, experts, scholars, or ordinary people
- Companies and businesses, including their official accounts
- Organizations such as universities, associations, NGOs, and unions
- Government departments and regulators
- Media organizations such as newspapers, TV stations, self-media accounts, and websites
- Social media platforms themselves
- Representatives of specific groups such as alumni associations, fan communities, or rights-defense groups

**Not allowed**:
- Abstract concepts such as "public opinion", "emotion", or "trend"
- Topics or themes such as "academic integrity" or "education reform"
- Opinions or stances such as "supporters" or "opponents"

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

**Hierarchy requirement (must include both specific types and fallback types)**:

Your 10 entity types must follow this structure:

A. **Fallback types (required, placed as the last 2 items)**:
   - `Person`: fallback type for any natural person who does not fit a more specific person type.
   - `Organization`: fallback type for any organization that does not fit a more specific organization type.

B. **Specific types (8, designed from the text)**:
   - Design more specific types for the main roles that appear in the text
   - Example: for an academic incident, you might use `Student`, `Professor`, `University`
   - Example: for a business incident, you might use `Company`, `CEO`, `Employee`

**Why fallback types are needed**:
- The text may include many kinds of people, such as teachers, bystanders, or anonymous netizens
- If no specialized type fits them, they should be assigned to `Person`
- Likewise, small organizations or temporary groups should fall under `Organization`

**Design principles for specific types**:
- Identify high-frequency or central role types from the text
- Each specific type should have clear boundaries and avoid overlap
- The description must clearly explain how the type differs from the fallback type

### 2. Relationship type design

- Quantity: 6-10
- Relationships should reflect realistic social-media interactions
- Make sure `source_targets` covers the entity types you define

### 3. Attribute design

- Each entity type should have 1-3 key attributes
- **Note**: attribute names cannot use `name`, `uuid`, `group_id`, `created_at`, or `summary` because those are reserved words
- Recommended options include `full_name`, `title`, `role`, `position`, `location`, and `description`

## Entity type references

**Person types (specific)**:
- Student: student
- Professor: professor or scholar
- Journalist: journalist
- Celebrity: celebrity or influencer
- Executive: executive
- Official: government official
- Lawyer: lawyer
- Doctor: doctor

**Person type (fallback)**:
- Person: any natural person not covered by the specific types above

**Organization types (specific)**:
- University: university
- Company: company or business
- GovernmentAgency: government agency
- MediaOutlet: media organization
- Hospital: hospital
- School: primary or secondary school
- NGO: non-governmental organization

**Organization type (fallback)**:
- Organization: any organization not covered by the specific types above

## Relationship type references

- WORKS_FOR: works for
- STUDIES_AT: studies at
- AFFILIATED_WITH: is affiliated with
- REPRESENTS: represents
- REGULATES: regulates
- REPORTS_ON: reports on
- COMMENTS_ON: comments on
- RESPONDS_TO: responds to
- SUPPORTS: supports
- OPPOSES: opposes
- COLLABORATES_WITH: collaborates with
- COMPETES_WITH: competes with
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
Based on the information above, design entity types and relationship types suitable for social opinion simulation.

**Rules that must be followed**:
1. Output exactly 10 entity types
2. The last 2 must be fallback types: Person (person fallback) and Organization (organization fallback)
3. The first 8 must be specific types designed from the text
4. All entity types must be real actors that can speak or act, not abstract concepts
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
        return entity_lookup.get(normalized_key)
    
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
        
        # Zep API limits: at most 10 custom entity types and 10 custom edge types.
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10
        
        # Fallback type definitions.
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        # Check whether fallback types already exist.
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # Fallback types that need to be added.
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # Remove existing types if adding fallbacks would exceed the limit.
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # Calculate how many types need to be removed.
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # Remove from the end to preserve earlier, likely more important specific types.
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # Add the fallback types.
            result["entity_types"].extend(fallbacks_to_add)
        
        # Final defensive limit enforcement.
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
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
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
