"""
Intelligent simulation configuration generator.
Uses an LLM to generate detailed simulation parameters from simulation
requirements, document content, and graph data.

The workflow is fully automated and does not require manual parameter setup.
It uses a staged generation strategy to avoid failures caused by producing too
much content at once:
1. Generate time configuration
2. Generate event configuration
3. Generate agent configuration in batches
4. Generate platform configuration
"""

import json
import math
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime

from openai import OpenAI

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.simulation_config')

# Daily activity schedule for users in China (Beijing time)
CHINA_TIMEZONE_CONFIG = {
    # Late night period with almost no activity
    "dead_hours": [0, 1, 2, 3, 4, 5],
    # Morning period as activity ramps up
    "morning_hours": [6, 7, 8],
    # Workday period
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    # Evening peak period
    "peak_hours": [19, 20, 21, 22],
    # Night period with declining activity
    "night_hours": [23],
    # Activity multipliers
    "activity_multipliers": {
        "dead": 0.05,      # Almost nobody is active after midnight
        "morning": 0.4,    # Activity gradually rises in the morning
        "work": 0.7,       # Moderate activity during working hours
        "peak": 1.5,       # Evening peak activity
        "night": 0.5       # Activity drops late at night
    }
}


@dataclass
class AgentActivityConfig:
    """Activity configuration for a single agent."""
    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str
    
    # Activity level (0.0-1.0)
    activity_level: float = 0.5  # Overall activity level
    
    # Posting frequency (expected actions per hour)
    posts_per_hour: float = 1.0
    comments_per_hour: float = 2.0
    
    # Active hours (24-hour clock, 0-23)
    active_hours: List[int] = field(default_factory=lambda: list(range(8, 23)))
    
    # Response speed to trending events, in simulated minutes
    response_delay_min: int = 5
    response_delay_max: int = 60
    
    # Sentiment bias (-1.0 to 1.0, negative to positive)
    sentiment_bias: float = 0.0
    
    # Stance toward the topic
    stance: str = "neutral"  # supportive, opposing, neutral, observer
    
    # Influence weight, affecting how likely others are to see this agent's content
    influence_weight: float = 1.0


@dataclass  
class TimeSimulationConfig:
    """Time simulation configuration based on common China-based activity patterns."""
    # Total simulation duration in hours
    total_simulation_hours: int = 72  # Default: 72 hours (3 days)
    
    # Time represented by each round, in simulated minutes
    minutes_per_round: int = 60
    
    # Range of agents activated per hour
    agents_per_hour_min: int = 5
    agents_per_hour_max: int = 20
    
    # Peak hours, typically 19:00-22:00
    peak_hours: List[int] = field(default_factory=lambda: [19, 20, 21, 22])
    peak_activity_multiplier: float = 1.5
    
    # Off-peak hours, typically 00:00-05:00 with minimal activity
    off_peak_hours: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5])
    off_peak_activity_multiplier: float = 0.05  # Very low activity after midnight
    
    # Morning hours
    morning_hours: List[int] = field(default_factory=lambda: [6, 7, 8])
    morning_activity_multiplier: float = 0.4
    
    # Working hours
    work_hours: List[int] = field(default_factory=lambda: [9, 10, 11, 12, 13, 14, 15, 16, 17, 18])
    work_activity_multiplier: float = 0.7


@dataclass
class EventConfig:
    """Event configuration."""
    # Initial events triggered at the start of the simulation
    initial_posts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Scheduled events triggered at specific times
    scheduled_events: List[Dict[str, Any]] = field(default_factory=list)
    
    # Trending topic keywords
    hot_topics: List[str] = field(default_factory=list)
    
    # Narrative direction of the discussion
    narrative_direction: str = ""


@dataclass
class PlatformConfig:
    """Platform-specific configuration."""
    platform: str  # twitter or reddit
    
    # Recommendation algorithm weights
    recency_weight: float = 0.4  # Recency
    popularity_weight: float = 0.3  # Popularity
    relevance_weight: float = 0.3  # Relevance
    
    # Viral spread threshold
    viral_threshold: int = 10
    
    # Echo chamber strength
    echo_chamber_strength: float = 0.5


@dataclass
class SimulationParameters:
    """Complete simulation parameter set."""
    # Basic information
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str
    
    # Time configuration
    time_config: TimeSimulationConfig = field(default_factory=TimeSimulationConfig)
    
    # Agent configurations
    agent_configs: List[AgentActivityConfig] = field(default_factory=list)
    
    # Event configuration
    event_config: EventConfig = field(default_factory=EventConfig)
    
    # Platform configuration
    twitter_config: Optional[PlatformConfig] = None
    reddit_config: Optional[PlatformConfig] = None
    
    # LLM configuration
    llm_model: str = ""
    llm_base_url: str = ""
    
    # Generation metadata
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    generation_reasoning: str = ""  # LLM reasoning summary
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary."""
        time_dict = asdict(self.time_config)
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "time_config": time_dict,
            "agent_configs": [asdict(a) for a in self.agent_configs],
            "event_config": asdict(self.event_config),
            "twitter_config": asdict(self.twitter_config) if self.twitter_config else None,
            "reddit_config": asdict(self.reddit_config) if self.reddit_config else None,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
            "generation_reasoning": self.generation_reasoning,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class SimulationConfigGenerator:
    """
    Intelligent simulation configuration generator.

    Uses an LLM to analyze simulation requirements, document content, and graph
    entities, then automatically generate an appropriate simulation parameter set.

    It uses a staged generation strategy:
    1. Generate time and event configuration first
    2. Generate agent configuration in 10-20 item batches
    3. Generate platform configuration
    """
    
    # Maximum context length in characters
    MAX_CONTEXT_LENGTH = 50000
    # Number of agents generated per batch
    AGENTS_PER_BATCH = 15
    
    # Context truncation lengths per step
    TIME_CONFIG_CONTEXT_LENGTH = 10000   # Time configuration
    EVENT_CONFIG_CONTEXT_LENGTH = 8000   # Event configuration
    ENTITY_SUMMARY_LENGTH = 300          # Entity summary
    AGENT_SUMMARY_LENGTH = 300           # Entity summary inside agent configuration
    ENTITIES_PER_TYPE_DISPLAY = 20       # Display count per entity type
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        Generate the full simulation configuration in staged steps.

        Args:
            simulation_id: Simulation ID
            project_id: Project ID
            graph_id: Graph ID
            simulation_requirement: Simulation requirement description
            document_text: Raw document content
            entities: Filtered entity list
            enable_twitter: Whether Twitter is enabled
            enable_reddit: Whether Reddit is enabled
            progress_callback: Progress callback with `(current_step, total_steps, message)`

        Returns:
            SimulationParameters: Full simulation parameters
        """
        logger.info(
            f"Starting intelligent simulation configuration generation: "
            f"simulation_id={simulation_id}, entity_count={len(entities)}"
        )
        
        # Calculate the total number of steps.
        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches  # time config + event config + N agent batches + platform config
        current_step = 0
        
        def report_progress(step: int, message: str):
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")
        
        # 1. Build the base context.
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities
        )
        
        reasoning_parts = []
        
        # ========== Step 1: Generate time configuration ==========
        report_progress(1, "Generating time configuration...")
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"Time configuration: {time_config_result.get('reasoning', 'Succeeded')}")
        
        # ========== Step 2: Generate event configuration ==========
        report_progress(2, "Generating event configuration and hot topics...")
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(f"Event configuration: {event_config_result.get('reasoning', 'Succeeded')}")
        
        # ========== Step 3-N: Generate agent configuration in batches ==========
        all_agent_configs = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]
            
            report_progress(
                3 + batch_idx,
                f"Generating agent configuration ({start_idx + 1}-{end_idx}/{len(entities)})..."
            )
            
            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement
            )
            all_agent_configs.extend(batch_configs)
        
        reasoning_parts.append(f"Agent configuration: successfully generated {len(all_agent_configs)} items")
        
        # ========== Assign agents to initial posts ==========
        logger.info("Assigning suitable poster agents for initial posts...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len([p for p in event_config.initial_posts if p.get("poster_agent_id") is not None])
        reasoning_parts.append(f"Initial post assignment: assigned posters to {assigned_count} posts")
        
        # ========== Final step: Generate platform configuration ==========
        report_progress(total_steps, "Generating platform configuration...")
        twitter_config = None
        reddit_config = None
        
        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5
            )
        
        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6
            )
        
        # Build the final parameters.
        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts)
        )
        
        logger.info(f"Simulation configuration generation completed: {len(params.agent_configs)} agent configs")
        
        return params
    
    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode]
    ) -> str:
        """Build the LLM context and truncate it to the maximum length."""
        
        # Entity summary.
        entity_summary = self._summarize_entities(entities)
        
        # Build the context.
        context_parts = [
            f"## Simulation Requirement\n{simulation_requirement}",
            f"\n## Entity Information ({len(entities)})\n{entity_summary}",
        ]
        
        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500  # Leave a small safety margin.
        
        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(document truncated)"
            context_parts.append(f"\n## Original Document Content\n{doc_text}")
        
        return "\n".join(context_parts)
    
    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """Generate an entity summary."""
        lines = []
        
        # Group entities by type.
        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)
        
        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)})")
            # Use the configured display count and summary length.
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                summary_preview = (e.summary[:summary_len] + "...") if len(e.summary) > summary_len else e.summary
                lines.append(f"- {e.name}: {summary_preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ... and {len(type_entities) - display_count} more")
        
        return "\n".join(lines)
    
    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Call the LLM with retries and basic JSON repair logic."""
        import re
        
        max_attempts = 3
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # Lower temperature on each retry.
                    # Do not set max_tokens so the LLM can respond freely.
                )
                
                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason
                
                # Check whether the response was truncated.
                if finish_reason == 'length':
                    logger.warning(f"LLM output was truncated (attempt {attempt+1})")
                    content = self._fix_truncated_json(content)
                
                # Try to parse the JSON.
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed (attempt {attempt+1}): {str(e)[:80]}")
                    
                    # Try to repair the JSON.
                    fixed = self._try_fix_config_json(content)
                    if fixed:
                        return fixed
                    
                    last_error = e
                    
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(2 * (attempt + 1))
        
        raise last_error or Exception("LLM call failed")
    
    def _fix_truncated_json(self, content: str) -> str:
        """Repair truncated JSON."""
        content = content.strip()
        
        # Count unclosed braces and brackets.
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # Close an unfinished string if needed.
        if content and content[-1] not in '",}]':
            content += '"'
        
        # Close remaining brackets and braces.
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_config_json(self, content: str) -> Optional[Dict[str, Any]]:
        """Try to repair configuration JSON."""
        import re
        
        # Repair truncated content first.
        content = self._fix_truncated_json(content)
        
        # Extract the JSON portion.
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # Remove newlines inside strings.
            def fix_string(match):
                s = match.group(0)
                s = s.replace('\n', ' ').replace('\r', ' ')
                s = re.sub(r'\s+', ' ', s)
                return s
            
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)
            
            try:
                return json.loads(json_str)
            except:
                # Try removing all control characters.
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass
        
        return None
    
    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """Generate time configuration."""
        # Use the configured context truncation length.
        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]
        
        # Calculate the maximum allowed per-hour count.
        max_agents_allowed = max(1, int(num_entities * 0.9))
        
        prompt = f"""Generate a time simulation configuration based on the following simulation requirements.

{context_truncated}

## Task
Generate a JSON time configuration.

### General principles (for reference only; adjust them to the event and participants):
- The user base is assumed to be in China, so the schedule should fit Beijing time habits
- Almost no activity from 00:00-05:00 (activity multiplier 0.05)
- Activity gradually rises from 06:00-08:00 (activity multiplier 0.4)
- Moderate activity during working hours from 09:00-18:00 (activity multiplier 0.7)
- Peak activity from 19:00-22:00 (activity multiplier 1.5)
- Activity declines after 23:00 (activity multiplier 0.5)
- Typical pattern: low after midnight, increasing in the morning, moderate during work hours, highest in the evening
- **Important**: the example values below are only references. Adjust the actual time ranges based on the event and participants.
  - Example: student groups may peak between 21:00-23:00; media may stay active all day; official institutions may only be active during work hours
  - Example: a breaking event may also trigger late-night discussion, so `off_peak_hours` can be shortened

### Return JSON only (no markdown)

Example:
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": "Explanation for the selected time configuration"
}}

Field descriptions:
- total_simulation_hours (int): total simulation duration, 24-168 hours; shorter for breaking events, longer for ongoing topics
- minutes_per_round (int): duration of each round, 30-120 minutes; 60 is recommended
- agents_per_hour_min (int): minimum number of active agents per hour (range: 1-{max_agents_allowed})
- agents_per_hour_max (int): maximum number of active agents per hour (range: 1-{max_agents_allowed})
- peak_hours (int array): peak time range, adjusted to the participant profile
- off_peak_hours (int array): low-activity hours, usually after midnight
- morning_hours (int array): morning hours
- work_hours (int array): work hours
- reasoning (string): brief explanation for the configuration"""

        system_prompt = "You are a social media simulation expert. Return pure JSON, and make the time configuration match typical user activity patterns in China."
        
        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Time configuration LLM generation failed: {e}. Falling back to defaults")
            return self._get_default_time_config(num_entities)
    
    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """Get the default time configuration."""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # One hour per round to speed up simulated time
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "Using the default China-based activity schedule (1 hour per round)"
        }
    
    def _parse_time_config(self, result: Dict[str, Any], num_entities: int) -> TimeSimulationConfig:
        """Parse time configuration and ensure per-hour counts do not exceed total agents."""
        # Get the raw values.
        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))
        
        # Validate and correct values so they do not exceed the total number of agents.
        if agents_per_hour_min > num_entities:
            logger.warning(
                f"agents_per_hour_min ({agents_per_hour_min}) exceeded the total agent count "
                f"({num_entities}) and was corrected"
            )
            agents_per_hour_min = max(1, num_entities // 10)
        
        if agents_per_hour_max > num_entities:
            logger.warning(
                f"agents_per_hour_max ({agents_per_hour_max}) exceeded the total agent count "
                f"({num_entities}) and was corrected"
            )
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)
        
        # Ensure min < max.
        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(f"agents_per_hour_min >= max and was corrected to {agents_per_hour_min}")
        
        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),  # Default: one hour per round
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # Almost no activity after midnight
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5
        )
    
    def _generate_event_config(
        self, 
        context: str, 
        simulation_requirement: str,
        entities: List[EntityNode]
    ) -> Dict[str, Any]:
        """Generate event configuration."""
        
        # Collect available entity types for the LLM.
        entity_types_available = list(set(
            e.get_entity_type() or "Unknown" for e in entities
        ))
        
        # List representative entity names for each type.
        type_examples = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)
        
        type_info = "\n".join([
            f"- {t}: {', '.join(examples)}" 
            for t, examples in type_examples.items()
        ])
        
        # Use the configured context truncation length.
        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]
        
        prompt = f"""Generate event configuration based on the following simulation requirements.

Simulation requirement: {simulation_requirement}

{context_truncated}

## Available entity types and examples
{type_info}

## Task
Generate event configuration JSON:
- extract hot-topic keywords
- describe the narrative direction
- design initial post content, and **every post must specify `poster_type`**

**Important**: `poster_type` must be chosen from the available entity types above so that each initial post can be assigned to a suitable agent.
For example, official statements should come from Official or University types, news should come from MediaOutlet, and student opinions should come from Student.

Return JSON only (no markdown):
{{
    "hot_topics": ["keyword1", "keyword2", ...],
    "narrative_direction": "<description of how the discussion evolves>",
    "initial_posts": [
        {{"content": "post content", "poster_type": "entity type (must come from the available types)"}},
        ...
    ],
    "reasoning": "<brief explanation>"
}}"""

        system_prompt = "You are a public-opinion analysis expert. Return pure JSON. `poster_type` must exactly match one of the available entity types."
        
        try:
            return self._call_llm_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.warning(f"Event configuration LLM generation failed: {e}. Falling back to defaults")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "Using default configuration"
            }
    
    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """Parse the event configuration result."""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", "")
        )
    
    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig]
    ) -> EventConfig:
        """
        Assign a suitable poster agent to each initial post.

        Match the best `agent_id` for each post based on its `poster_type`.
        """
        if not event_config.initial_posts:
            return event_config
        
        # Build an agent index by entity type.
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)
        
        # Type alias mapping for format variations from the LLM.
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }
        
        # Track used agent indexes per type to avoid reusing the same agent repeatedly.
        used_indices: Dict[str, int] = {}
        
        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")
            
            # Try to find a matching agent.
            matched_agent_id = None
            
            # 1. Direct match
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. Alias-based match
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break
            
            # 3. If still unmatched, use the most influential agent.
            if matched_agent_id is None:
                logger.warning(
                    f"No matching agent found for type '{poster_type}'. "
                    f"Using the most influential agent instead"
                )
                if agent_configs:
                    # Sort by influence and pick the highest.
                    sorted_agents = sorted(agent_configs, key=lambda a: a.influence_weight, reverse=True)
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0
            
            updated_posts.append({
                "content": content,
                "poster_type": post.get("poster_type", "Unknown"),
                "poster_agent_id": matched_agent_id
            })
            
            logger.info(f"Initial post assignment: poster_type='{poster_type}' -> agent_id={matched_agent_id}")
        
        event_config.initial_posts = updated_posts
        return event_config
    
    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str
    ) -> List[AgentActivityConfig]:
        """Generate agent configuration in batches."""
        
        # Build entity input data using the configured summary length.
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else ""
            })
        
        prompt = f"""Generate social media activity configuration for each entity based on the following information.

Simulation requirement: {simulation_requirement}

## Entity list
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## Task
Generate activity configuration for each entity, following these guidelines:
- **Time pattern matches user activity in China**: almost inactive from 00:00-05:00, most active from 19:00-22:00
- **Official institutions** (`University` / `GovernmentAgency`): low activity (0.1-0.3), active during work hours (9-17), slow response (60-240 minutes), high influence (2.5-3.0)
- **Media** (`MediaOutlet`): medium activity (0.4-0.6), active all day (8-23), fast response (5-30 minutes), high influence (2.0-2.5)
- **Individuals** (`Student` / `Person` / `Alumni`): high activity (0.6-0.9), mainly active in the evening (18-23), fast response (1-15 minutes), lower influence (0.8-1.2)
- **Public figures / experts**: medium activity (0.4-0.6), medium-high influence (1.5-2.0)

Return JSON only (no markdown):
{{
    "agent_configs": [
        {{
            "agent_id": <must match the input>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <posting frequency>,
            "comments_per_hour": <comment frequency>,
            "active_hours": [<active hour list, aligned with user activity in China>],
            "response_delay_min": <minimum response delay in minutes>,
            "response_delay_max": <maximum response delay in minutes>,
            "sentiment_bias": <-1.0 to 1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <influence weight>
        }},
        ...
    ]
}}"""

        system_prompt = "You are a social media behavior analysis expert. Return pure JSON and make the configuration align with user activity patterns in China."
        
        try:
            result = self._call_llm_with_retry(prompt, system_prompt)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"Agent configuration batch LLM generation failed: {e}. Falling back to rule-based generation")
            llm_configs = {}
        
        # Build `AgentActivityConfig` objects.
        configs = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})
            
            # Fall back to rule-based generation when the LLM does not return a config.
            if not cfg:
                cfg = self._generate_agent_config_by_rule(entity)
            
            config = AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0)
            )
            configs.append(config)
        
        return configs
    
    def _generate_agent_config_by_rule(self, entity: EntityNode) -> Dict[str, Any]:
        """Generate a single agent configuration using rule-based defaults."""
        entity_type = (entity.get_entity_type() or "Unknown").lower()
        
        if entity_type in ["university", "governmentagency", "ngo"]:
            # Official institutions: working hours only, low frequency, high influence
            return {
                "activity_level": 0.2,
                "posts_per_hour": 0.1,
                "comments_per_hour": 0.05,
                "active_hours": list(range(9, 18)),  # 9:00-17:59
                "response_delay_min": 60,
                "response_delay_max": 240,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 3.0
            }
        elif entity_type in ["mediaoutlet"]:
            # Media: active throughout the day, medium frequency, high influence
            return {
                "activity_level": 0.5,
                "posts_per_hour": 0.8,
                "comments_per_hour": 0.3,
                "active_hours": list(range(7, 24)),  # 7:00-23:59
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "observer",
                "influence_weight": 2.5
            }
        elif entity_type in ["professor", "expert", "official"]:
            # Experts/professors: active during work hours and evenings, medium frequency
            return {
                "activity_level": 0.4,
                "posts_per_hour": 0.3,
                "comments_per_hour": 0.5,
                "active_hours": list(range(8, 22)),  # 8:00-21:59
                "response_delay_min": 15,
                "response_delay_max": 90,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 2.0
            }
        elif entity_type in ["student"]:
            # Students: mainly active in the evening, high frequency
            return {
                "activity_level": 0.8,
                "posts_per_hour": 0.6,
                "comments_per_hour": 1.5,
                "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # Morning + evening
                "response_delay_min": 1,
                "response_delay_max": 15,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 0.8
            }
        elif entity_type in ["alumni"]:
            # Alumni: mainly active in the evening
            return {
                "activity_level": 0.6,
                "posts_per_hour": 0.4,
                "comments_per_hour": 0.8,
                "active_hours": [12, 13, 19, 20, 21, 22, 23],  # Lunch break + evening
                "response_delay_min": 5,
                "response_delay_max": 30,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
        else:
            # General public: evening peak activity
            return {
                "activity_level": 0.7,
                "posts_per_hour": 0.5,
                "comments_per_hour": 1.2,
                "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # Daytime + evening
                "response_delay_min": 2,
                "response_delay_max": 20,
                "sentiment_bias": 0.0,
                "stance": "neutral",
                "influence_weight": 1.0
            }
    
