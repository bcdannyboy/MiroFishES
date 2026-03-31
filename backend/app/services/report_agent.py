"""
Report Agent service.
Uses LangChain + Zep to generate simulation reports with a ReACT workflow.

Capabilities:
1. Generate reports from simulation requirements and Zep graph information
2. Plan the outline first, then generate content section by section
3. Use multi-round ReACT reasoning and reflection for each section
4. Support user chat with autonomous retrieval tool usage
"""

import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .phase_timing import PhaseTimingRecorder
from .zep_tools import (
    ZepToolsService, 
    SearchResult, 
    InsightForgeResult, 
    PanoramaResult,
    InterviewResult
)

logger = get_logger('mirofish.report_agent')


class ReportLogger:
    """
    Detailed Report Agent logger.

    Creates an `agent_log.jsonl` file in the report folder to record every step.
    Each line is a complete JSON object with timestamps, action types, details, and more.
    """
    
    def __init__(self, report_id: str):
        """
        Initialize the logger.

        Args:
            report_id: Report ID, used to determine the log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'agent_log.jsonl'
        )
        self.start_time = datetime.now()
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        """Ensure the log file directory exists."""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _get_elapsed_time(self) -> float:
        """Get elapsed time in seconds since initialization."""
        return (datetime.now() - self.start_time).total_seconds()
    
    def log(
        self, 
        action: str, 
        stage: str,
        details: Dict[str, Any],
        section_title: str = None,
        section_index: int = None
    ):
        """
        Record a log entry.

        Args:
            action: Action type, such as 'start', 'tool_call', 'llm_response', or 'section_complete'
            stage: Current stage, such as 'planning', 'generating', or 'completed'
            details: Detailed content dictionary, not truncated
            section_title: Current section title, optional
            section_index: Current section index, optional
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": round(self._get_elapsed_time(), 2),
            "report_id": self.report_id,
            "action": action,
            "stage": stage,
            "section_title": section_title,
            "section_index": section_index,
            "details": details
        }
        
        # Append to the JSONL log file.
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    def log_start(self, simulation_id: str, graph_id: str, simulation_requirement: str):
        """Record the start of report generation."""
        self.log(
            action="report_start",
            stage="pending",
            details={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "simulation_requirement": simulation_requirement,
                "message": "Report generation task started"
            }
        )
    
    def log_planning_start(self):
        """Record the start of outline planning."""
        self.log(
            action="planning_start",
            stage="planning",
            details={"message": "Starting report outline planning"}
        )
    
    def log_planning_context(self, context: Dict[str, Any]):
        """Record context collected during planning."""
        self.log(
            action="planning_context",
            stage="planning",
            details={
                "message": "Retrieved simulation context information",
                "context": context
            }
        )
    
    def log_planning_complete(self, outline_dict: Dict[str, Any]):
        """Record outline planning completion."""
        self.log(
            action="planning_complete",
            stage="planning",
            details={
                "message": "Outline planning completed",
                "outline": outline_dict
            }
        )
    
    def log_section_start(self, section_title: str, section_index: int):
        """Record the start of section generation."""
        self.log(
            action="section_start",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={"message": f"Starting section generation: {section_title}"}
        )
    
    def log_react_thought(self, section_title: str, section_index: int, iteration: int, thought: str):
        """Record a ReACT thought step."""
        self.log(
            action="react_thought",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "thought": thought,
                "message": f"ReACT thought round {iteration}"
            }
        )
    
    def log_tool_call(
        self, 
        section_title: str, 
        section_index: int,
        tool_name: str, 
        parameters: Dict[str, Any],
        iteration: int
    ):
        """Record a tool call."""
        self.log(
            action="tool_call",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "parameters": parameters,
                "message": f"Calling tool: {tool_name}"
            }
        )
    
    def log_tool_result(
        self,
        section_title: str,
        section_index: int,
        tool_name: str,
        result: str,
        iteration: int
    ):
        """Record a tool result without truncation."""
        self.log(
            action="tool_result",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "tool_name": tool_name,
                "result": result,  # Store the full result without truncation.
                "result_length": len(result),
                "message": f"Tool {tool_name} returned a result"
            }
        )
    
    def log_llm_response(
        self,
        section_title: str,
        section_index: int,
        response: str,
        iteration: int,
        has_tool_calls: bool,
        has_final_answer: bool
    ):
        """Record an LLM response without truncation."""
        self.log(
            action="llm_response",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "iteration": iteration,
                "response": response,  # Store the full response without truncation.
                "response_length": len(response),
                "has_tool_calls": has_tool_calls,
                "has_final_answer": has_final_answer,
                "message": f"LLM response (tool calls: {has_tool_calls}, final answer: {has_final_answer})"
            }
        )
    
    def log_section_content(
        self,
        section_title: str,
        section_index: int,
        content: str,
        tool_calls_count: int
    ):
        """Record generated section content only, not full section completion."""
        self.log(
            action="section_content",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": content,  # Store the full content without truncation.
                "content_length": len(content),
                "tool_calls_count": tool_calls_count,
                "message": f"Section content generated: {section_title}"
            }
        )
    
    def log_section_full_complete(
        self,
        section_title: str,
        section_index: int,
        full_content: str
    ):
        """
        Record full section completion.

        The frontend should watch this log entry to determine when a section is truly complete
        and retrieve its final content.
        """
        self.log(
            action="section_complete",
            stage="generating",
            section_title=section_title,
            section_index=section_index,
            details={
                "content": full_content,
                "content_length": len(full_content),
                "message": f"Section generation completed: {section_title}"
            }
        )
    
    def log_report_complete(self, total_sections: int, total_time_seconds: float):
        """Record report generation completion."""
        self.log(
            action="report_complete",
            stage="completed",
            details={
                "total_sections": total_sections,
                "total_time_seconds": round(total_time_seconds, 2),
                "message": "Report generation completed"
            }
        )
    
    def log_error(self, error_message: str, stage: str, section_title: str = None):
        """Record an error."""
        self.log(
            action="error",
            stage=stage,
            section_title=section_title,
            section_index=None,
            details={
                "error": error_message,
                "message": f"Error occurred: {error_message}"
            }
        )


class ReportConsoleLogger:
    """
    Console-style logger for Report Agent.

    Writes console-style logs such as INFO and WARNING into `console_log.txt`
    inside the report folder. Unlike `agent_log.jsonl`, these logs are plain text.
    """
    
    def __init__(self, report_id: str):
        """
        Initialize the console logger.

        Args:
            report_id: Report ID, used to determine the log file path
        """
        self.report_id = report_id
        self.log_file_path = os.path.join(
            Config.UPLOAD_FOLDER, 'reports', report_id, 'console_log.txt'
        )
        self._ensure_log_file()
        self._file_handler = None
        self._setup_file_handler()
    
    def _ensure_log_file(self):
        """Ensure the log file directory exists."""
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
    
    def _setup_file_handler(self):
        """Configure the file handler so logs are also written to disk."""
        import logging
        
        # Create the file handler.
        self._file_handler = logging.FileHandler(
            self.log_file_path,
            mode='a',
            encoding='utf-8'
        )
        self._file_handler.setLevel(logging.INFO)
        
        # Use the same compact format as the console output.
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self._file_handler.setFormatter(formatter)
        
        # Attach the handler to report_agent-related loggers.
        loggers_to_attach = [
            'mirofish.report_agent',
            'mirofish.zep_tools',
        ]
        
        for logger_name in loggers_to_attach:
            target_logger = logging.getLogger(logger_name)
            # Avoid attaching the same handler more than once.
            if self._file_handler not in target_logger.handlers:
                target_logger.addHandler(self._file_handler)
    
    def close(self):
        """Close the file handler and detach it from the loggers."""
        import logging
        
        if self._file_handler:
            loggers_to_detach = [
                'mirofish.report_agent',
                'mirofish.zep_tools',
            ]
            
            for logger_name in loggers_to_detach:
                target_logger = logging.getLogger(logger_name)
                if self._file_handler in target_logger.handlers:
                    target_logger.removeHandler(self._file_handler)
            
            self._file_handler.close()
            self._file_handler = None
    
    def __del__(self):
        """Ensure the file handler is closed during destruction."""
        self.close()


class ReportStatus(str, Enum):
    """Report status."""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReportSection:
    """Report section."""
    title: str
    content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content
        }

    def to_markdown(self, level: int = 2) -> str:
        """Convert to Markdown."""
        md = f"{'#' * level} {self.title}\n\n"
        if self.content:
            md += f"{self.content}\n\n"
        return md


@dataclass
class ReportOutline:
    """Report outline."""
    title: str
    summary: str
    sections: List[ReportSection]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [s.to_dict() for s in self.sections]
        }
    
    def to_markdown(self) -> str:
        """Convert to Markdown."""
        md = f"# {self.title}\n\n"
        md += f"> {self.summary}\n\n"
        for section in self.sections:
            md += section.to_markdown()
        return md


@dataclass
class Report:
    """Full report."""
    report_id: str
    simulation_id: str
    graph_id: str
    simulation_requirement: str
    status: ReportStatus
    outline: Optional[ReportOutline] = None
    markdown_content: str = ""
    created_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None
    ensemble_id: Optional[str] = None
    cluster_id: Optional[str] = None
    run_id: Optional[str] = None
    probabilistic_context: Optional[Dict[str, Any]] = None
    base_graph_id: Optional[str] = None
    runtime_graph_id: Optional[str] = None
    graph_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.base_graph_id and self.graph_id:
            self.base_graph_id = self.graph_id
        if not self.graph_id and self.base_graph_id:
            self.graph_id = self.base_graph_id
        if not self.graph_ids:
            self.graph_ids = [
                candidate
                for candidate in [self.base_graph_id, self.runtime_graph_id]
                if candidate
            ]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "base_graph_id": self.base_graph_id or self.graph_id,
            "runtime_graph_id": self.runtime_graph_id,
            "graph_ids": self.graph_ids,
            "simulation_requirement": self.simulation_requirement,
            "status": self.status.value,
            "outline": self.outline.to_dict() if self.outline else None,
            "markdown_content": self.markdown_content,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "ensemble_id": self.ensemble_id,
            "cluster_id": self.cluster_id,
            "run_id": self.run_id,
            "probabilistic_context": self.probabilistic_context,
        }


# ===============================================================
# Prompt template constants
# ===============================================================

# Tool descriptions

TOOL_DESC_INSIGHT_FORGE = """\
InsightForge: deep retrieval for advanced analysis.
This is our most powerful retrieval function. It will:
1. Automatically break your question into multiple sub-questions
2. Retrieve information from multiple dimensions of the simulation graph
3. Combine semantic search, entity analysis, and relationship-chain tracing
4. Return the most comprehensive and in-depth retrieval results

Best used when:
- You need a deep analysis of a topic
- You need to understand multiple aspects of an event
- You need rich supporting material for a report section

Returns:
- Original relevant facts that can be quoted directly
- Core entity insights
- Relationship-chain analysis"""

TOOL_DESC_PANORAMA_SEARCH = """\
PanoramaSearch: broad retrieval for the full picture.
Use this tool to understand the complete simulation outcome, especially how events evolved. It will:
1. Retrieve all relevant nodes and relationships
2. Distinguish between currently valid facts and historical or expired facts
3. Help you understand how public opinion evolved over time

Best used when:
- You need the full development arc of an event
- You need to compare public sentiment across different phases
- You need comprehensive entity and relationship information

Returns:
- Currently valid facts (latest simulation results)
- Historical or expired facts (evolution records)
- All involved entities"""

TOOL_DESC_QUICK_SEARCH = """\
QuickSearch: lightweight fast retrieval.
This tool is best for simple and direct information lookups.

Best used when:
- You need to quickly find a specific fact
- You need to verify a particular claim
- You need simple information retrieval

Returns:
- A list of facts most relevant to the query"""

TOOL_DESC_INTERVIEW_AGENTS = """\
InterviewAgents: real agent interviews across both platforms.
This calls the OASIS simulation interview API to interview running simulation agents directly.
It is not an LLM roleplay. It fetches original answers from the actual simulation agents.
By default, it interviews agents on both Twitter and Reddit to capture broader perspectives.

Workflow:
1. Automatically read the profile files to understand all simulation agents
2. Intelligently select the agents most relevant to the interview topic, such as students, media, or officials
3. Automatically generate interview questions
4. Call `/api/simulation/interview/batch` to conduct real interviews on both platforms
5. Combine all interview results into a multi-perspective analysis

Best used when:
- You need views on an event from different roles, such as students, media, or officials
- You need to collect multiple opinions and positions
- You need authentic responses from simulation agents in the OASIS environment
- You want the report to feel more vivid with direct interview excerpts

Returns:
- Identity information for the interviewed agents
- Their interview responses on both Twitter and Reddit
- Key quotes that can be cited directly
- An interview summary and comparison of viewpoints

Important: the OASIS simulation environment must be running to use this tool."""

# Outline planning prompt

PLAN_SYSTEM_PROMPT = """\
You are an expert writer of simulation-backed forecast reports. You can inspect forecast artifacts, simulation evidence, events, speech, and interactions inside the simulation world.

Core idea:
We created a simulation world and injected a specific simulation requirement as the condition under study. The resulting events are a bounded simulated scenario from this modeled setting. They are not experimental data, not a literal view into the real future, and not direct evidence of real human behavior.
When a forecast object is attached, it is the primary object to summarize first. Simulation-market and scenario artifacts remain supporting evidence and must keep their bounded semantics explicit.

Your task:
Write a concise simulation-backed forecast report that answers:
1. What forecast question and latest forecast answer are in scope?
2. What happened inside this simulated scenario under the conditions we set?
3. How did different agents or groups react and act within this simulated environment?
4. What risks, tensions, or possible implications emerged within this scenario and deserve attention?

Report positioning:
- This is a forecast-object-first report with bounded simulation evidence about a scoped modeled setting
- If a forecast object is attached, lead with the forecast question, latest answer, resolution/scoring state, and any simulation-market provenance or disagreement status
- Focus on event trajectories, group reactions, emergent phenomena, uncertainties, and possible implications within the simulation
- Agent behavior and statements are simulated outputs, not direct stand-ins for real human behavior outside the model
- Do not write it as a literal forecast, certainty claim, or analysis of the current real world
- Do not write it as a generic public-opinion summary
- Use bounded language such as "in this simulation", "within this scenario", "may", "could", or "suggests"

Section count limits:
- Minimum 2 sections, maximum 5 sections
- No subsections are needed; each section should contain complete content on its own
- Keep the content concise and focused on the core scenario findings
- Design the section structure yourself based on the simulation results

Output the report outline in JSON using this format:
{
    "title": "Report title",
    "summary": "Report summary (one sentence capturing the core scenario finding)",
    "sections": [
        {
            "title": "Section title",
            "description": "Description of the section content"
        }
    ]
}

Important: the `sections` array must contain at least 2 items and at most 5 items."""

PLAN_USER_PROMPT_TEMPLATE = """\
Scenario under study:
The condition injected into the simulation world (simulation requirement): {simulation_requirement}

Simulation world scale:
- Number of entities in the simulation: {total_nodes}
- Number of relationships generated between entities: {total_edges}
- Entity type distribution: {entity_types}
- Number of active agents: {total_entities}

Sample simulated facts observed in the run:
{related_facts_json}

Review this simulated scenario:
1. What kind of scenario state emerged under the conditions we set?
2. How did different groups of people or agents react and act?
3. What risks, tensions, or possible implications deserve attention?

Design the most appropriate report section structure based on the simulation results.

Reminder: the report must have between 2 and 5 sections, and the content should stay concise and focused on the core scenario findings."""

# Section generation prompt

SECTION_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert writer of simulation-backed forecast reports, and you are writing one section of the report.

Report title: {report_title}
Report summary: {report_summary}
Scenario under study (simulation requirement): {simulation_requirement}

Current section to write: {section_title}

===============================================================
Core idea
===============================================================

The simulation world is a bounded simulated scenario. We injected a specific condition, the simulation requirement, into the world.
Agent behavior and interactions in the simulation are simulated outputs from this modeled setting, not direct evidence of real human behavior.
If a forecast object is attached to the report context, treat it as the primary object for the section and use simulation evidence to support or qualify it rather than replacing it.

Your job is to:
- Describe what happened inside the simulated scenario under the given conditions
- Analyze how different groups of people or agents reacted and acted within this scenario
- Identify risks, tensions, and opportunities that this scenario may suggest

Do not write this as an analysis of the current real world.
Focus on what the simulation shows within its own scope. Use bounded language and avoid certainty claims about the real future.

===============================================================
Most important rules: must follow
===============================================================

1. You must call tools to observe the simulation world.
   - You are observing a bounded modeled scenario from a global view
   - All content must come from events and agent behavior inside the simulation world
   - Do not use your own knowledge to write the report
   - Each section must call tools at least 3 times and at most 5 times to observe the simulation world

2. You must quote original agent behavior and statements.
   - Agent speech and behavior are simulated outputs, not direct stand-ins for real human behavior outside the model
   - Show those outputs using quote formatting, for example:
     > "A certain group of people might say: original quoted content..."
   - These quotations are the core evidence for this simulation scenario report

3. Language consistency: quoted content must be translated into the report language.
   - Tool results may contain English or mixed Chinese and English phrasing
   - If the simulation requirement and source materials are in Chinese, the report must be written entirely in Chinese
   - When you quote English or mixed-language content returned by tools, you must translate it into fluent Chinese before writing it into the report
   - Preserve the original meaning while making the expression natural and smooth
   - This rule applies to both body text and quote blocks using `>` formatting

4. Present scenario results faithfully.
   - The report content must reflect the simulation results from this modeled setting
   - Do not add information that does not exist in the simulation
   - If there is not enough information about a topic, state that honestly
   - Use bounded language and avoid certainty claims about the real world

===============================================================
Formatting rules: extremely important
===============================================================

One section is the smallest content unit.
- Each section is the smallest building block of the report
- Do not use any Markdown headings inside the section, such as `#`, `##`, `###`, or `####`
- Do not add the section title again at the beginning of the content
- The system adds the section title automatically; you should write body content only
- Use bold text, paragraph separation, quotes, and lists to organize the content, but do not use headings

Correct example:
```
This section analyzes how public opinion around the event spread. Based on a close reading of the simulation data, we found that...

**Initial ignition stage**

Twitter served as the first field of public discussion and played the core role in launching the information:

> "Twitter contributed 68% of the initial volume..."

**Emotional amplification stage**

The second platform further amplified the event's influence:

- Strong visual impact
- High emotional resonance
```

Incorrect example:
```
## Executive Summary          <- Wrong. Do not add any headings
### 1. Initial Stage          <- Wrong. Do not use `###` subsections
#### 1.1 Detailed Analysis    <- Wrong. Do not use `####` sub-subsections

This section analyzes...
```

===============================================================
Available retrieval tools (call 3 to 5 times per section)
===============================================================

{tools_description}

Tool usage guidance: mix different tools rather than relying on just one.
- `insight_forge`: deep analysis that automatically decomposes the question and retrieves facts and relationships from multiple dimensions
- `panorama_search`: broad panoramic search for the full picture, timeline, and evolution of the event
- `quick_search`: quickly verify a specific information point
- `interview_agents`: interview simulation agents to get first-person viewpoints and authentic reactions from different roles

===============================================================
Workflow
===============================================================

In each reply, you may do only one of the following two things, never both:

Option A: call a tool.
Output your reasoning, then call one tool using this format:
<tool_call>
{{"name": "tool_name", "parameters": {{"parameter_name": "parameter_value"}}}}
</tool_call>
The system will execute the tool and return the result to you. You do not need to and must not invent tool results yourself.

Option B: output the final content.
When you have gathered enough information through tools, output the section content starting with `Final Answer:`.

Strictly forbidden:
- Do not include both a tool call and `Final Answer` in the same reply
- Do not invent tool results or observations yourself; all tool results are injected by the system
- Call at most one tool per reply

===============================================================
Section content requirements
===============================================================

1. The content must be based on simulation data retrieved by tools
2. Use many original quotations to show what the simulation produced
3. Use Markdown, but never headings:
   - Use `**bold text**` to mark key points instead of subheadings
   - Use lists such as `-` or `1. 2. 3.` to organize points
   - Separate different paragraphs with blank lines
   - Never use heading syntax such as `#`, `##`, `###`, or `####`
4. Quote formatting rules: each quote must stand as its own paragraph.
   A quote must be separated by blank lines before and after it. Do not mix it into a paragraph.

   Correct format:
   ```
   The school's response was seen as lacking substance.

   > "The school's response pattern appeared rigid and slow in the fast-changing social media environment."

   This evaluation reflects widespread public dissatisfaction.
   ```

   Incorrect format:
   ```
   The school's response was seen as lacking substance. > "The school's response pattern..." This evaluation reflects...
   ```
5. Maintain logical continuity with the other sections
6. Avoid repetition. Read the completed section content below carefully and do not repeat the same information
7. To repeat: do not add any headings. Use bold text instead of subsection titles."""

SECTION_USER_PROMPT_TEMPLATE = """\
Completed section content already written. Read carefully and avoid repetition:
{previous_content}

===============================================================
Current task: write section `{section_title}`
===============================================================

Important reminders:
1. Read the completed sections above carefully and avoid repeating the same content
2. You must call tools to retrieve simulation data before you start writing
3. Mix different tools instead of using only one
4. The report must come from retrieval results, not your own knowledge

Formatting warning: must follow
- Do not write any headings of any level, including `#`, `##`, `###`, or `####`
- Do not begin with `{section_title}`
- The section title is added automatically by the system
- Write body text directly and use bold text instead of subsection headings

Begin now:
1. First think about what information this section needs
2. Then call tools to obtain simulation data
3. After collecting enough information, output `Final Answer` with pure body text and no headings"""

# Messages used inside the ReACT loop

REACT_OBSERVATION_TEMPLATE = """\
Observation (retrieval result):

=== Tool `{tool_name}` returned ===
{result}

===============================================================
Tools called: {tool_calls_count}/{max_tool_calls} (used: {used_tools_str}){unused_hint}
- If the information is sufficient, output the section content starting with `Final Answer:` and quote the source text above
- If you need more information, call one more tool to continue retrieving
==============================================================="""

REACT_INSUFFICIENT_TOOLS_MSG = (
    "Note: you have called tools only {tool_calls_count} times, but at least {min_tool_calls} calls are required. "
    "Call another tool to gather more simulation data before outputting Final Answer. {unused_hint}"
)

REACT_INSUFFICIENT_TOOLS_MSG_ALT = (
    "You have called tools only {tool_calls_count} times so far, but at least {min_tool_calls} calls are required. "
    "Call a tool to retrieve simulation data. {unused_hint}"
)

REACT_TOOL_LIMIT_MSG = (
    "The tool-call limit has been reached ({tool_calls_count}/{max_tool_calls}); you cannot call more tools. "
    'Immediately output the section content based on the information already gathered, starting with "Final Answer:".'
)

REACT_UNUSED_TOOLS_HINT = "\nTip: you have not used these tools yet: {unused_list}. Try different tools to gather information from multiple angles."

REACT_FORCE_FINAL_MSG = "The tool-call limit has been reached. Output Final Answer directly and generate the section content."

# Chat prompt

CHAT_SYSTEM_PROMPT_TEMPLATE = """\
You are a concise and efficient simulation report assistant.

Background:
Forecast condition: {simulation_requirement}

Generated analysis report:
{report_content}

Scoped probabilistic report context for this exact report or report request:
{probabilistic_context}

Rules:
1. Prioritize answering based on the report content above
2. Answer directly and avoid long reasoning monologues
3. Only call tools when the report content is insufficient to answer the question
4. Keep answers concise, clear, and well-structured

Available tools: use only if needed, and call at most 1 to 2 times
{tools_description}

Tool call format:
<tool_call>
{{"name": "tool_name", "parameters": {{"parameter_name": "parameter_value"}}}}
</tool_call>

Answering style:
- Be concise and direct; do not write long essays
- Use `>` formatting to quote key content
- Give the conclusion first, then explain the reasoning"""

CHAT_OBSERVATION_SUFFIX = "\n\nAnswer the question concisely."


# ===============================================================
# ReportAgent main class
# ===============================================================


class ReportAgent:
    """
    Report Agent for simulation report generation.

    Uses a ReACT (Reasoning + Acting) workflow:
    1. Planning stage: analyze the simulation requirements and plan the report structure
    2. Generation stage: produce content section by section, with multiple tool calls per section
    3. Reflection stage: check content completeness and accuracy
    """
    
    # Maximum number of tool calls per section
    MAX_TOOL_CALLS_PER_SECTION = 5
    
    # Maximum number of reflection rounds
    MAX_REFLECTION_ROUNDS = 3
    
    # Maximum number of tool calls during chat
    MAX_TOOL_CALLS_PER_CHAT = 2
    
    def __init__(
        self, 
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None,
        report_id: Optional[str] = None,
        probabilistic_context: Optional[Dict[str, Any]] = None,
        graph_ids: Optional[List[str]] = None,
        base_graph_id: Optional[str] = None,
        runtime_graph_id: Optional[str] = None,
    ):
        """
        Initialize the Report Agent.
        
        Args:
            graph_id: Graph ID
            simulation_id: Simulation ID
            simulation_requirement: Simulation requirement description
            llm_client: LLM client, optional
            zep_tools: Zep tools service, optional
        """
        self.graph_id = base_graph_id or graph_id
        self.base_graph_id = self.graph_id
        self.runtime_graph_id = runtime_graph_id
        combined_graph_ids = []
        for candidate in [self.base_graph_id, *(graph_ids or []), self.runtime_graph_id]:
            if candidate and candidate not in combined_graph_ids:
                combined_graph_ids.append(candidate)
        self.graph_ids = combined_graph_ids
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement
        self.report_id = report_id
        self.probabilistic_context = probabilistic_context
        
        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()
        
        # Tool definitions
        self.tools = self._define_tools()
        
        # Loggers are initialized in generate_report.
        self.report_logger: Optional[ReportLogger] = None
        self.console_logger: Optional[ReportConsoleLogger] = None
        
        logger.info(
            "ReportAgent initialized: graph_id=%s graph_ids=%s simulation_id=%s",
            self.graph_id,
            self.graph_ids,
            simulation_id,
        )

    def _get_chat_report_context(self) -> tuple[str, Optional[Dict[str, Any]]]:
        """Load the exact saved report content for chat when one report is in scope."""
        report_content = ""
        report_context = self.probabilistic_context

        try:
            report = None
            if self.report_id:
                report = ReportManager.get_report(self.report_id)
            if report is None:
                report = ReportManager.get_report_for_scope(
                    self.simulation_id,
                    legacy_only=True,
                )

            if report and report.markdown_content:
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [Report content truncated] ..."
            if (
                self.report_id
                and report
                and report.probabilistic_context
                and report_context is None
            ):
                report_context = report.probabilistic_context
        except Exception as e:
            logger.warning(f"Failed to load report content: {e}")

        return report_content, report_context

    @staticmethod
    def _format_chat_probabilistic_context(
        probabilistic_context: Optional[Dict[str, Any]],
    ) -> str:
        """Keep probabilistic chat grounding explicit without overflowing the prompt."""
        if not probabilistic_context:
            return "(No saved probabilistic context for this report.)"

        context_text = json.dumps(
            ReportAgent._build_prompt_safe_probabilistic_context(
                probabilistic_context
            ),
            ensure_ascii=False,
            indent=2,
        )
        if len(context_text) > 4000:
            context_text = context_text[:4000] + "\n... [Probabilistic context truncated] ..."
        return context_text

    @staticmethod
    def _build_prompt_safe_grounding_context(
        probabilistic_context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Keep upstream grounding explicit and bounded for prompts."""
        if not probabilistic_context:
            return None

        grounding_context = probabilistic_context.get("grounding_context")
        if not isinstance(grounding_context, dict):
            return None

        evidence_items = grounding_context.get("evidence_items")
        if not isinstance(evidence_items, list):
            evidence_items = []

        return {
            "status": grounding_context.get("status", "unavailable"),
            "boundary_note": grounding_context.get("boundary_note"),
            "citation_counts": grounding_context.get("citation_counts", {}),
            "warnings": grounding_context.get("warnings", []),
            "evidence_items": [
                {
                    "citation_id": item.get("citation_id"),
                    "kind": item.get("kind"),
                    "title": item.get("title"),
                    "summary": item.get("summary"),
                    "locator": item.get("locator"),
                }
                for item in evidence_items[:4]
                if isinstance(item, dict)
            ],
        }

    @classmethod
    def _build_prompt_safe_forecast_workspace_context(
        cls,
        probabilistic_context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not probabilistic_context:
            return None

        workspace = probabilistic_context.get("forecast_workspace")
        if not isinstance(workspace, dict):
            return None

        forecast_question = workspace.get("forecast_question")
        if not isinstance(forecast_question, dict):
            forecast_question = {}

        evidence_bundle = workspace.get("evidence_bundle")
        if not isinstance(evidence_bundle, dict):
            evidence_bundle = {}

        prediction_ledger = workspace.get("prediction_ledger")
        if not isinstance(prediction_ledger, dict):
            prediction_ledger = {}

        latest_answer = workspace.get("forecast_answer")
        if not isinstance(latest_answer, dict):
            latest_answer = {}

        latest_answer_payload = latest_answer.get("answer_payload")
        if not isinstance(latest_answer_payload, dict):
            latest_answer_payload = {}

        supported_question_templates = []
        for template in (forecast_question.get("supported_question_templates") or [])[:3]:
            if not isinstance(template, dict):
                continue
            supported_question_templates.append(
                {
                    "template_id": template.get("template_id"),
                    "label": template.get("label"),
                    "question_type": template.get("question_type"),
                    "prompt_template": template.get("prompt_template"),
                    "required_fields": (template.get("required_fields") or [])[:6],
                    "abstain_guidance": template.get("abstain_guidance"),
                    "notes": (template.get("notes") or [])[:3],
                }
            )

        worker_comparison = workspace.get("worker_comparison")
        if not isinstance(worker_comparison, dict):
            worker_comparison = {}

        abstain_state = workspace.get("abstain_state")
        if not isinstance(abstain_state, dict):
            abstain_state = {}

        evaluation_results = workspace.get("evaluation_results")
        if not isinstance(evaluation_results, dict):
            evaluation_results = {}

        truthfulness_surface = workspace.get("truthfulness_surface")
        if not isinstance(truthfulness_surface, dict):
            truthfulness_surface = {}

        forecast_answer_summary = {
            "answer_id": latest_answer.get("answer_id"),
            "answer_type": latest_answer.get("answer_type"),
            "summary": latest_answer.get("summary"),
            "confidence_semantics": latest_answer.get("confidence_semantics"),
            "created_at": latest_answer.get("created_at"),
            "prediction_entry_ids": (latest_answer.get("prediction_entry_ids") or [])[:4],
            "worker_ids": (latest_answer.get("worker_ids") or [])[:4],
            "answer_payload": {
                "abstain": latest_answer_payload.get("abstain"),
                "abstain_reason": latest_answer_payload.get("abstain_reason"),
                "best_estimate": latest_answer_payload.get("best_estimate"),
                "counterevidence": (latest_answer_payload.get("counterevidence") or [])[:4],
                "assumption_summary": latest_answer_payload.get("assumption_summary"),
                "uncertainty_decomposition": latest_answer_payload.get(
                    "uncertainty_decomposition"
                ),
                "evaluation_summary": latest_answer_payload.get("evaluation_summary"),
                "confidence_basis": latest_answer_payload.get("confidence_basis"),
                "simulation_context": latest_answer_payload.get("simulation_context"),
            },
        }

        return {
            "forecast_question": {
                "forecast_id": forecast_question.get("forecast_id"),
                "title": forecast_question.get("title"),
                "question_text": forecast_question.get("question_text"),
                "question_type": forecast_question.get("question_type"),
                "horizon": forecast_question.get("horizon"),
                "issue_timestamp": forecast_question.get("issue_timestamp"),
                "owner": forecast_question.get("owner"),
                "source": forecast_question.get("source"),
                "abstention_conditions": (forecast_question.get("abstention_conditions") or [])[:4],
                "supported_question_templates": supported_question_templates,
            },
            "forecast_workspace_status": workspace.get("forecast_workspace_status"),
            "evidence_bundle": {
                "bundle_id": evidence_bundle.get("bundle_id"),
                "status": evidence_bundle.get("status"),
                "title": evidence_bundle.get("title"),
                "summary": evidence_bundle.get("summary"),
                "boundary_note": evidence_bundle.get("boundary_note"),
                "quality_summary": evidence_bundle.get("quality_summary"),
                "retrieval_quality": evidence_bundle.get("retrieval_quality"),
                "freshness_summary": evidence_bundle.get("freshness_summary"),
                "relevance_summary": evidence_bundle.get("relevance_summary"),
                "conflict_summary": evidence_bundle.get("conflict_summary"),
                "missing_evidence_markers": (evidence_bundle.get("missing_evidence_markers") or [])[:4],
                "uncertainty_summary": evidence_bundle.get("uncertainty_summary"),
                "source_entries": (evidence_bundle.get("source_entries") or evidence_bundle.get("entries") or [])[:5],
                "provider_snapshots": (evidence_bundle.get("provider_snapshots") or evidence_bundle.get("providers") or [])[:5],
            },
            "prediction_ledger": {
                "final_resolution_state": prediction_ledger.get("final_resolution_state"),
                "resolved_at": prediction_ledger.get("resolved_at"),
                "resolution_note": prediction_ledger.get("resolution_note"),
                "entry_count": len(prediction_ledger.get("entries") or []),
                "worker_output_count": len(prediction_ledger.get("worker_outputs") or []),
                "resolution_history_count": len(prediction_ledger.get("resolution_history") or []),
                "entries": (prediction_ledger.get("entries") or [])[:5],
                "worker_outputs": (prediction_ledger.get("worker_outputs") or [])[:5],
                "resolution_history": (prediction_ledger.get("resolution_history") or [])[:5],
            },
            "evaluation_results": {
                "status": evaluation_results.get("status"),
                "case_count": evaluation_results.get("case_count"),
                "resolved_case_count": evaluation_results.get("resolved_case_count"),
                "pending_case_count": evaluation_results.get("pending_case_count"),
                "cases": (evaluation_results.get("cases") or [])[:5],
            },
            "abstain_state": {
                "abstain": abstain_state.get("abstain"),
                "abstain_reason": abstain_state.get("abstain_reason"),
                "summary": abstain_state.get("summary"),
            },
            "forecast_answer": forecast_answer_summary,
            "worker_comparison": {
                "worker_count": worker_comparison.get("worker_count"),
                "worker_kinds": (worker_comparison.get("worker_kinds") or [])[:5],
                "worker_contribution_trace": (worker_comparison.get("worker_contribution_trace") or [])[:5],
                "abstain": worker_comparison.get("abstain"),
                "abstain_reason": worker_comparison.get("abstain_reason"),
                "best_estimate": worker_comparison.get("best_estimate"),
                "simulation_context": worker_comparison.get("simulation_context"),
            },
            "truthfulness_surface": truthfulness_surface,
        }

    @classmethod
    def _build_prompt_safe_probabilistic_context(
        cls,
        probabilistic_context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Format scoped probabilistic evidence without dumping entire artifacts."""
        if not probabilistic_context:
            return {}

        context = probabilistic_context
        return {
            "ensemble_id": context.get("ensemble_id"),
            "cluster_id": context.get("cluster_id"),
            "run_id": context.get("run_id"),
            "scope": context.get("scope"),
            "forecast_object": context.get("forecast_object"),
            "simulation_market_summary": context.get("simulation_market_summary"),
            "signal_provenance_summary": context.get("signal_provenance_summary"),
            "grounding_context": cls._build_prompt_safe_grounding_context(context),
            "probability_semantics": context.get("probability_semantics"),
            "confidence_status": context.get("confidence_status"),
            "calibration_provenance": context.get("calibration_provenance"),
            "quality_summary": context.get("quality_summary"),
            "forecast_workspace": cls._build_prompt_safe_forecast_workspace_context(context),
            "top_outcomes": (context.get("top_outcomes") or [])[:3],
            "scenario_families": (context.get("scenario_families") or [])[:2],
            "selected_cluster": context.get("selected_cluster"),
            "representative_runs": (context.get("representative_runs") or [])[:3],
            "selected_run": context.get("selected_run"),
            "sensitivity_overview": context.get("sensitivity_overview"),
            "driver_analysis": context.get("driver_analysis"),
            "compare_options": (context.get("compare_options") or [])[:3],
            "compare_catalog": {
                "boundary_note": ((context.get("compare_catalog") or {}).get("boundary_note")),
                "options": (((context.get("compare_catalog") or {}).get("options")) or [])[:3],
            } if context.get("compare_catalog") else None,
            "selected_compare": context.get("selected_compare"),
        }
    
    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define the available tools."""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "The question or topic you want to analyze in depth",
                    "report_context": "Context for the current report section (optional, helps generate more precise sub-questions)"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "Search query used for relevance ranking",
                    "include_expired": "Whether to include expired or historical content (default: True)"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "Search query string",
                    "limit": "Number of results to return (optional, default: 10)"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "Interview topic or requirement description (for example: 'Understand students' views on the dorm formaldehyde incident')",
                    "max_agents": "Maximum number of agents to interview (optional, default: 5, max: 10)"
                }
            }
        }
    
    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        Execute a tool call.
        
        Args:
            tool_name: Tool name
            parameters: Tool parameters
            report_context: Report context, used for InsightForge
            
        Returns:
            Tool result as text
        """
        logger.info(f"Executing tool: {tool_name}, parameters: {parameters}")
        
        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    graph_ids=self.graph_ids,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()
            
            elif tool_name == "panorama_search":
                # Breadth-first search to get the full picture.
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id,
                    graph_ids=self.graph_ids,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()
            
            elif tool_name == "quick_search":
                # Lightweight search for quick retrieval.
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id,
                    graph_ids=self.graph_ids,
                    query=query,
                    limit=limit
                )
                return result.to_text()
            
            elif tool_name == "interview_agents":
                # In-depth interviews using the real OASIS interview API for simulated agent responses across both platforms.
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                return result.to_text()
            
            # ========== Backward-compatible legacy tools (internally redirected to new tools) ==========
            
            elif tool_name == "search_graph":
                # Redirect to quick_search.
                logger.info("search_graph redirected to quick_search")
                return self._execute_tool("quick_search", parameters, report_context)
            
            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(
                    self.graph_id,
                    graph_ids=self.graph_ids,
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    graph_ids=self.graph_ids,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            elif tool_name == "get_simulation_context":
                # Redirect to insight_forge because it is more powerful.
                logger.info("get_simulation_context redirected to insight_forge")
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)
            
            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    graph_ids=self.graph_ids,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)
            
            else:
                return f"Unknown tool: {tool_name}. Use one of: insight_forge, panorama_search, quick_search"
                
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {str(e)}")
            return f"Tool execution failed: {str(e)}"
    
    # Valid tool names used when validating fallback parsing of raw JSON.
    VALID_TOOL_NAMES = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from an LLM response.

        Supported formats, in priority order:
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. Raw JSON where the whole response, or one line, is a tool call payload
        """
        tool_calls = []

        # Format 1: XML-style wrapper (standard format).
        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # Format 2: fallback when the LLM outputs raw JSON directly without <tool_call> tags.
        # Only try this if format 1 did not match, to avoid false positives in the main text.
        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # The response may contain reasoning text plus raw JSON, so try extracting the last JSON object.
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """Validate that the parsed JSON is a valid tool call."""
        # Support both {"name": ..., "parameters": ...} and {"tool": ..., "params": ...}.
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            # Normalize keys to name / parameters.
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False
    
    def _get_tools_description(self) -> str:
        """Build the tool description text."""
        desc_parts = ["Available tools:"]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  Parameters: {params_desc}")
        return "\n".join(desc_parts)

    def _build_probabilistic_prompt_context(
        self,
        *,
        max_chars: int = 5000,
    ) -> str:
        """Format scoped probabilistic evidence for prompt consumption."""
        if not self.probabilistic_context:
            return "(No scoped probabilistic report context available.)"

        prompt_payload = self._build_prompt_safe_probabilistic_context(
            self.probabilistic_context
        )
        context_text = json.dumps(prompt_payload, ensure_ascii=False, indent=2)
        if len(context_text) > max_chars:
            context_text = context_text[:max_chars] + "\n... [Probabilistic context truncated] ..."
        return context_text
    
    def plan_outline(
        self, 
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        Plan the report outline.
        
        Use the LLM to analyze the simulation requirements and plan the report structure.
        
        Args:
            progress_callback: Progress callback
            
        Returns:
            ReportOutline: Planned report outline
        """
        logger.info("Starting report outline planning...")
        
        if progress_callback:
            progress_callback("planning", 0, "Analyzing simulation requirements...")
        
        # Fetch simulation context first.
        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )
        
        if progress_callback:
            progress_callback("planning", 30, "Generating report outline...")
        
        system_prompt = PLAN_SYSTEM_PROMPT
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        )
        user_prompt += (
            "\n\nScoped probabilistic evidence for this exact report request:\n"
            f"{self._build_probabilistic_prompt_context(max_chars=5000)}"
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            if progress_callback:
                progress_callback("planning", 80, "Parsing outline structure...")
            
            # Parse the outline.
            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))
            
            outline = ReportOutline(
                title=response.get("title", "Simulation Analysis Report"),
                summary=response.get("summary", ""),
                sections=sections
            )
            
            if progress_callback:
                progress_callback("planning", 100, "Outline planning completed")
            
            logger.info(f"Outline planning completed: {len(sections)} sections")
            return outline
            
        except Exception as e:
            logger.error(f"Outline planning failed: {str(e)}")
            # Return a default outline with three sections as a fallback.
            return ReportOutline(
                title="Simulation Scenario Report",
                summary="Observed scenario dynamics and possible risks from the simulation run",
                sections=[
                    ReportSection(title="Scenario Dynamics and Key Findings"),
                    ReportSection(title="Group Responses Within the Simulation"),
                    ReportSection(title="Observed Risks and Open Questions")
                ]
            )
    
    def _generate_section_react(
        self, 
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        Generate content for a single section with a ReACT workflow.
        
        ReACT loop:
        1. Thought: analyze what information is needed
        2. Action: call tools to gather information
        3. Observation: analyze the tool results
        4. Repeat until the information is sufficient or the max count is reached
        5. Final Answer: generate the section content
        
        Args:
            section: Section to generate
            outline: Full outline
            previous_sections: Prior section content, used to maintain continuity
            progress_callback: Progress callback
            section_index: Section index, used for logging
            
        Returns:
            Section content in Markdown
        """
        logger.info(f"Generating section with ReACT: {section.title}")
        
        # Record the section start.
        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)
        
        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )

        # Build the user prompt and include up to 4000 characters from each completed section.
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                # Limit each prior section to 4000 characters.
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "(This is the first section)"
        
        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )
        user_prompt += (
            "\n\nScoped probabilistic evidence for this exact report request:\n"
            f"{self._build_probabilistic_prompt_context(max_chars=5000)}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # ReACT loop
        tool_calls_count = 0
        max_iterations = 5  # Maximum number of iterations.
        min_tool_calls = 3  # Minimum number of tool calls.
        conflict_retries = 0  # Consecutive conflicts where a tool call and Final Answer appear together.
        used_tools = set()  # Track tools that have already been used.
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        # Report context used for InsightForge sub-question generation.
        report_context = f"Section title: {section.title}\nSimulation requirement: {self.simulation_requirement}"
        
        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating", 
                    int((iteration / max_iterations) * 100),
                    f"Running deep retrieval and drafting ({tool_calls_count}/{self.MAX_TOOL_CALLS_PER_SECTION})"
                )
            
            # Call the LLM.
            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            # Check whether the LLM returned None because of an API issue or empty content.
            if response is None:
                logger.warning(f"Section {section.title}, iteration {iteration + 1}: LLM returned None")
                # If more iterations remain, append a message and retry.
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "(The response was empty)"})
                    messages.append({"role": "user", "content": "Please continue generating the content."})
                    continue
                # If the last iteration also returned None, exit the loop and force a finish.
                break

            logger.debug(f"LLM response: {response[:200]}...")

            # Parse once and reuse the result.
            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # Handle the case where the LLM outputs both a tool call and a Final Answer.
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    f"Section {section.title}, round {iteration+1}: "
                    f"LLM output both a tool call and a Final Answer (conflict #{conflict_retries})"
                )

                if conflict_retries <= 2:
                    # For the first two conflicts, discard the response and ask the LLM to reply again.
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[Format error] Your reply included both a tool call and a Final Answer, which is not allowed.\n"
                            "Each reply may do only one of the following:\n"
                            "- Call one tool (output a single <tool_call> block and do not write a Final Answer)\n"
                            "- Output the final content (start with 'Final Answer:' and do not include <tool_call>)\n"
                            "Reply again and do only one of these."
                        ),
                    })
                    continue
                else:
                    # On the third conflict, degrade gracefully by truncating to the first tool call and forcing execution.
                    logger.warning(
                        f"Section {section.title}: {conflict_retries} consecutive conflicts; "
                        "degrading to execute only the first tool call"
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # Record the LLM response.
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # Case 1: the LLM produced a Final Answer.
            if has_final_answer:
                # If too few tools have been called, reject the answer and ask for more tool usage.
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = (
                        f"(These tools have not been used yet; consider using them: {', '.join(unused_tools)})"
                        if unused_tools else ""
                    )
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                # Normal completion.
                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(f"Section {section.title} generated successfully (tool calls: {tool_calls_count})")

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # Case 2: the LLM is trying to call a tool.
            if has_tool_calls:
                # If the tool budget is exhausted, explicitly ask for a Final Answer.
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                # Execute only the first tool call.
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(f"LLM attempted {len(tool_calls)} tool calls; executing only the first: {call['name']}")

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                # Build a hint listing unused tools.
                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list=", ".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # Case 3: the LLM returned neither a tool call nor a Final Answer.
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                # Too few tool calls so far; recommend unused tools.
                unused_tools = all_tools - used_tools
                unused_hint = (
                    f"(These tools have not been used yet; consider using them: {', '.join(unused_tools)})"
                    if unused_tools else ""
                )

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # Enough tool calls have been made, and the LLM returned content without the "Final Answer:" prefix.
            # Accept that content directly as the final answer instead of looping again.
            logger.info(
                f"Section {section.title} had no 'Final Answer:' prefix; accepting the LLM output directly "
                f"as the final content (tool calls: {tool_calls_count})"
            )
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer
        
        # Force generation after reaching the maximum number of iterations.
        logger.warning(f"Section {section.title} reached the maximum number of iterations; forcing completion")
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})
        
        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        # Check whether the LLM returned None during the forced-final pass.
        if response is None:
            logger.error(f"Section {section.title}: forced-final pass returned None; using the default error message")
            final_answer = "(Section generation failed: the LLM returned an empty response. Please try again later.)"
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response
        
        # Record section content generation completion.
        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )
        
        return final_answer
    
    def generate_report(
        self, 
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        Generate the full report with section-by-section real-time output.
        
        Each completed section is saved immediately, without waiting for the entire report to finish.
        File structure:
        reports/{report_id}/
            meta.json       - report metadata
            outline.json    - report outline
            progress.json   - generation progress
            section_01.md   - section 1
            section_02.md   - section 2
            ...
            full_report.md  - complete report
        
        Args:
            progress_callback: Progress callback function (stage, progress, message)
            report_id: Report ID, optional. Generated automatically if omitted.
            
        Returns:
            Report: Full report
        """
        import uuid
        
        # Generate a report_id automatically if one is not provided.
        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()
        
        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            base_graph_id=self.base_graph_id,
            runtime_graph_id=self.runtime_graph_id,
            graph_ids=self.graph_ids,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )

        # Titles of completed sections for progress tracking.
        completed_section_titles = []
        phase_timing = PhaseTimingRecorder(
            artifact_path=os.path.join(
                ReportManager._get_report_folder(report_id),
                "report_phase_timings.json",
            ),
            scope_kind="report",
            scope_id=report_id,
        )

        try:
            with phase_timing.measure_phase(
                "report_synthesis",
                metadata={"simulation_id": self.simulation_id},
            ) as phase_metadata:
                # Initialization: create the report folder and save the initial state.
                ReportManager._ensure_report_folder(report_id)
                
                # Initialize the structured logger.
                self.report_logger = ReportLogger(report_id)
                self.report_logger.log_start(
                    simulation_id=self.simulation_id,
                    graph_id=self.graph_id,
                    simulation_requirement=self.simulation_requirement
                )
                
                # Initialize the console logger.
                self.console_logger = ReportConsoleLogger(report_id)
                
                ReportManager.update_progress(
                    report_id, "pending", 0, "Initializing report...",
                    completed_sections=[]
                )
                ReportManager.save_report(report)
                
                # Stage 1: plan the outline.
                report.status = ReportStatus.PLANNING
                ReportManager.update_progress(
                    report_id, "planning", 5, "Starting report outline planning...",
                    completed_sections=[]
                )
                
                # Record the start of planning.
                self.report_logger.log_planning_start()
                
                if progress_callback:
                    progress_callback("planning", 0, "Starting report outline planning...")
                
                outline = self.plan_outline(
                    progress_callback=lambda stage, prog, msg: 
                        progress_callback(stage, prog // 5, msg) if progress_callback else None
                )
                report.outline = outline
                phase_metadata["section_count"] = len(outline.sections)
                
                # Record planning completion.
                self.report_logger.log_planning_complete(outline.to_dict())
                
                # Save the outline to disk.
                ReportManager.save_outline(report_id, outline)
                ReportManager.update_progress(
                    report_id, "planning", 15, f"Outline planning completed: {len(outline.sections)} sections",
                    completed_sections=[]
                )
                ReportManager.save_report(report)
                
                logger.info(f"Outline saved to file: {report_id}/outline.json")
                
                # Stage 2: generate the report section by section and save each section immediately.
                report.status = ReportStatus.GENERATING
                
                total_sections = len(outline.sections)
                generated_sections = []  # Preserve generated content for later section context.
                
                for i, section in enumerate(outline.sections):
                    section_num = i + 1
                    base_progress = 20 + int((i / total_sections) * 70)
                    
                    # Update progress.
                    ReportManager.update_progress(
                        report_id, "generating", base_progress,
                        f"Generating section: {section.title} ({section_num}/{total_sections})",
                        current_section=section.title,
                        completed_sections=completed_section_titles
                    )
                    
                    if progress_callback:
                        progress_callback(
                            "generating", 
                            base_progress, 
                            f"Generating section: {section.title} ({section_num}/{total_sections})"
                        )
                    
                    # Generate the main section content.
                    section_content = self._generate_section_react(
                        section=section,
                        outline=outline,
                        previous_sections=generated_sections,
                        progress_callback=lambda stage, prog, msg:
                            progress_callback(
                                stage, 
                                base_progress + int(prog * 0.7 / total_sections),
                                msg
                            ) if progress_callback else None,
                        section_index=section_num
                    )
                    
                    section.content = section_content
                    generated_sections.append(f"## {section.title}\n\n{section_content}")

                    # Save the section.
                    ReportManager.save_section(report_id, section_num, section)
                    completed_section_titles.append(section.title)

                    # Record section completion.
                    full_section_content = f"## {section.title}\n\n{section_content}"

                    if self.report_logger:
                        self.report_logger.log_section_full_complete(
                            section_title=section.title,
                            section_index=section_num,
                            full_content=full_section_content.strip()
                        )

                    logger.info(f"Section saved: {report_id}/section_{section_num:02d}.md")
                    
                    # Update progress.
                    ReportManager.update_progress(
                        report_id, "generating", 
                        base_progress + int(70 / total_sections),
                        f"Section completed: {section.title}",
                        current_section=None,
                        completed_sections=completed_section_titles
                    )
                
                # Stage 3: assemble the full report.
                if progress_callback:
                    progress_callback("generating", 95, "Assembling the full report...")
                
                ReportManager.update_progress(
                    report_id, "generating", 95, "Assembling the full report...",
                    completed_sections=completed_section_titles
                )
                
                # Assemble the full report via ReportManager.
                report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
                report.status = ReportStatus.COMPLETED
                report.completed_at = datetime.now().isoformat()
                
                # Compute total elapsed time.
                total_time_seconds = (datetime.now() - start_time).total_seconds()
                phase_metadata["total_time_seconds"] = round(total_time_seconds, 2)
                
                # Record report completion.
                if self.report_logger:
                    self.report_logger.log_report_complete(
                        total_sections=total_sections,
                        total_time_seconds=total_time_seconds
                    )
                
                # Save the final report.
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "completed", 100, "Report generation completed",
                    completed_sections=completed_section_titles
                )
                
                if progress_callback:
                    progress_callback("completed", 100, "Report generation completed")
                
                logger.info(f"Report generation completed: {report_id}")
                
                # Close the console logger.
                if self.console_logger:
                    self.console_logger.close()
                    self.console_logger = None
                
                return report
            
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            report.status = ReportStatus.FAILED
            report.error = str(e)
            
            # Record the error.
            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")
            
            # Save the failed state.
            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, f"Report generation failed: {str(e)}",
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass  # Ignore errors while saving the failed state.
            
            # Close the console logger.
            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None
            
            return report
    
    def chat(
        self, 
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Chat with the Report Agent.
        
        During chat, the agent can autonomously call retrieval tools to answer questions.
        
        Args:
            message: User message
            chat_history: Conversation history
            
        Returns:
            {
                "response": "Agent reply",
                "tool_calls": [list of tool calls],
                "sources": [information sources]
            }
        """
        logger.info(f"Report Agent chat: {message[:50]}...")
        
        chat_history = chat_history or []
        
        report_content, probabilistic_context = self._get_chat_report_context()
        
        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "(No report available yet)",
            probabilistic_context=self._format_chat_probabilistic_context(
                probabilistic_context
            ),
            tools_description=self._get_tools_description(),
        )

        # Build the message list.
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add recent chat history.
        for h in chat_history[-10:]:  # Limit history length.
            messages.append(h)
        
        # Add the user message.
        messages.append({
            "role": "user", 
            "content": message
        })
        
        # Simplified ReACT loop.
        tool_calls_made = []
        max_iterations = 2  # Keep the iteration count low.
        
        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )
            
            # Parse tool calls.
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                # No tool calls, so return the response directly.
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
                
                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }
            
            # Execute a limited number of tool calls.
            tool_results = []
            for call in tool_calls[:1]:  # Execute at most one tool call per round.
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500]  # Limit result length.
                })
                tool_calls_made.append(call)
            
            # Append the tool results to the conversation.
            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']} result]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })
        
        # After reaching the maximum iterations, request the final response.
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )
        
        # Clean the response.
        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)
        
        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }


class ReportManager:
    """
    Report manager.

    Handles report persistence and retrieval.

    File structure for section-by-section output:
    reports/
      {report_id}/
        meta.json          - report metadata and status
        outline.json       - report outline
        progress.json      - generation progress
        section_01.md      - section 1
        section_02.md      - section 2
        ...
        full_report.md     - complete report
    """
    
    # Report storage directory.
    REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'reports')
    
    @classmethod
    def _ensure_reports_dir(cls):
        """Ensure the root report directory exists."""
        os.makedirs(cls.REPORTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_report_folder(cls, report_id: str) -> str:
        """Get the report folder path."""
        return os.path.join(cls.REPORTS_DIR, report_id)
    
    @classmethod
    def _ensure_report_folder(cls, report_id: str) -> str:
        """Ensure the report folder exists and return its path."""
        folder = cls._get_report_folder(report_id)
        os.makedirs(folder, exist_ok=True)
        return folder
    
    @classmethod
    def _get_report_path(cls, report_id: str) -> str:
        """Get the report metadata file path."""
        return os.path.join(cls._get_report_folder(report_id), "meta.json")
    
    @classmethod
    def _get_report_markdown_path(cls, report_id: str) -> str:
        """Get the full report Markdown file path."""
        return os.path.join(cls._get_report_folder(report_id), "full_report.md")
    
    @classmethod
    def _get_outline_path(cls, report_id: str) -> str:
        """Get the outline file path."""
        return os.path.join(cls._get_report_folder(report_id), "outline.json")
    
    @classmethod
    def _get_progress_path(cls, report_id: str) -> str:
        """Get the progress file path."""
        return os.path.join(cls._get_report_folder(report_id), "progress.json")
    
    @classmethod
    def _get_section_path(cls, report_id: str, section_index: int) -> str:
        """Get the section Markdown file path."""
        return os.path.join(cls._get_report_folder(report_id), f"section_{section_index:02d}.md")
    
    @classmethod
    def _get_agent_log_path(cls, report_id: str) -> str:
        """Get the Agent log file path."""
        return os.path.join(cls._get_report_folder(report_id), "agent_log.jsonl")
    
    @classmethod
    def _get_console_log_path(cls, report_id: str) -> str:
        """Get the console log file path."""
        return os.path.join(cls._get_report_folder(report_id), "console_log.txt")
    
    @classmethod
    def get_console_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get console log content.

        These are console-style output logs from report generation, such as INFO and WARNING,
        and they differ from the structured entries in `agent_log.jsonl`.
        
        Args:
            report_id: Report ID
            from_line: First line to read, used for incremental fetches. `0` means from the start.
            
        Returns:
            {
                "logs": [list of log lines],
                "total_lines": total line count,
                "from_line": starting line number,
                "has_more": whether more logs remain
            }
        """
        log_path = cls._get_console_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    # Keep the original log line while stripping the trailing newline.
                    logs.append(line.rstrip('\n\r'))
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Already read to the end.
        }
    
    @classmethod
    def get_console_log_stream(cls, report_id: str) -> List[str]:
        """
        Get the full console log in a single call.
        
        Args:
            report_id: Report ID
            
        Returns:
            List of log lines
        """
        result = cls.get_console_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def get_agent_log(cls, report_id: str, from_line: int = 0) -> Dict[str, Any]:
        """
        Get Agent log content.
        
        Args:
            report_id: Report ID
            from_line: First line to read, used for incremental fetches. `0` means from the start.
            
        Returns:
            {
                "logs": [list of log entries],
                "total_lines": total line count,
                "from_line": starting line number,
                "has_more": whether more logs remain
            }
        """
        log_path = cls._get_agent_log_path(report_id)
        
        if not os.path.exists(log_path):
            return {
                "logs": [],
                "total_lines": 0,
                "from_line": 0,
                "has_more": False
            }
        
        logs = []
        total_lines = 0
        
        with open(log_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i >= from_line:
                    try:
                        log_entry = json.loads(line.strip())
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Skip lines that fail to parse.
                        continue
        
        return {
            "logs": logs,
            "total_lines": total_lines,
            "from_line": from_line,
            "has_more": False  # Already read to the end.
        }
    
    @classmethod
    def get_agent_log_stream(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get the full Agent log in a single call.
        
        Args:
            report_id: Report ID
            
        Returns:
            List of log entries
        """
        result = cls.get_agent_log(report_id, from_line=0)
        return result["logs"]
    
    @classmethod
    def save_outline(cls, report_id: str, outline: ReportOutline) -> None:
        """
        Save the report outline.

        Called immediately after the planning stage finishes.
        """
        cls._ensure_report_folder(report_id)
        
        with open(cls._get_outline_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(outline.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"Outline saved: {report_id}")
    
    @classmethod
    def save_section(
        cls,
        report_id: str,
        section_index: int,
        section: ReportSection
    ) -> str:
        """
        Save a single section.

        Called immediately after a section finishes so sections can be streamed incrementally.

        Args:
            report_id: Report ID
            section_index: Section index, starting from 1
            section: Section object

        Returns:
            Saved file path
        """
        cls._ensure_report_folder(report_id)

        # Build the section Markdown content and remove any duplicate headings.
        cleaned_content = cls._clean_section_content(section.content, section.title)
        md_content = f"## {section.title}\n\n"
        if cleaned_content:
            md_content += f"{cleaned_content}\n\n"

        # Save the file.
        file_suffix = f"section_{section_index:02d}.md"
        file_path = os.path.join(cls._get_report_folder(report_id), file_suffix)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        logger.info(f"Section saved: {report_id}/{file_suffix}")
        return file_path
    
    @classmethod
    def _clean_section_content(cls, content: str, section_title: str) -> str:
        """
        Clean section content.

        1. Remove Markdown heading lines at the start that duplicate the section title
        2. Convert all `###` and lower-level headings into bold text
        
        Args:
            content: Original content
            section_title: Section title
            
        Returns:
            Cleaned content
        """
        import re
        
        if not content:
            return content
        
        content = content.strip()
        lines = content.split('\n')
        cleaned_lines = []
        skip_next_empty = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Check whether the line is a Markdown heading.
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title_text = heading_match.group(2).strip()
                
                # Check for a heading that duplicates the section title within the first five lines.
                if i < 5:
                    if title_text == section_title or title_text.replace(' ', '') == section_title.replace(' ', ''):
                        skip_next_empty = True
                        continue
                
                # Convert all heading levels (`#`, `##`, `###`, `####`, etc.) into bold text.
                # The system already injects the section title, so content should not contain headings.
                cleaned_lines.append(f"**{title_text}**")
                cleaned_lines.append("")  # Add a blank line.
                continue
            
            # If the previous line was a skipped heading and this line is empty, skip it too.
            if skip_next_empty and stripped == '':
                skip_next_empty = False
                continue
            
            skip_next_empty = False
            cleaned_lines.append(line)
        
        # Remove leading blank lines.
        while cleaned_lines and cleaned_lines[0].strip() == '':
            cleaned_lines.pop(0)
        
        # Remove leading separators.
        while cleaned_lines and cleaned_lines[0].strip() in ['---', '***', '___']:
            cleaned_lines.pop(0)
            # Also remove blank lines immediately after the separator.
            while cleaned_lines and cleaned_lines[0].strip() == '':
                cleaned_lines.pop(0)
        
        return '\n'.join(cleaned_lines)
    
    @classmethod
    def update_progress(
        cls, 
        report_id: str, 
        status: str, 
        progress: int, 
        message: str,
        current_section: str = None,
        completed_sections: List[str] = None
    ) -> None:
        """
        Update report generation progress.

        The frontend can read `progress.json` to get real-time progress.
        """
        cls._ensure_report_folder(report_id)
        
        progress_data = {
            "status": status,
            "progress": progress,
            "message": message,
            "current_section": current_section,
            "completed_sections": completed_sections or [],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(cls._get_progress_path(report_id), 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def get_progress(cls, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report generation progress."""
        path = cls._get_progress_path(report_id)
        
        if not os.path.exists(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @classmethod
    def get_generated_sections(cls, report_id: str) -> List[Dict[str, Any]]:
        """
        Get the list of generated sections.

        Returns information for all saved section files.
        """
        folder = cls._get_report_folder(report_id)
        
        if not os.path.exists(folder):
            return []
        
        sections = []
        for filename in sorted(os.listdir(folder)):
            if filename.startswith('section_') and filename.endswith('.md'):
                file_path = os.path.join(folder, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse the section index from the filename.
                parts = filename.replace('.md', '').split('_')
                section_index = int(parts[1])

                sections.append({
                    "filename": filename,
                    "section_index": section_index,
                    "content": content
                })

        return sections
    
    @classmethod
    def assemble_full_report(cls, report_id: str, outline: ReportOutline) -> str:
        """
        Assemble the full report.

        Combine saved section files into a complete report and clean up the heading structure.
        """
        folder = cls._get_report_folder(report_id)
        
        # Build the report header.
        md_content = f"# {outline.title}\n\n"
        md_content += f"> {outline.summary}\n\n"
        md_content += f"---\n\n"
        
        # Read all section files in order.
        sections = cls.get_generated_sections(report_id)
        for section_info in sections:
            md_content += section_info["content"]
        
        # Post-process the report to clean up heading issues.
        md_content = cls._post_process_report(md_content, outline)
        
        # Save the full report.
        full_path = cls._get_report_markdown_path(report_id)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        logger.info(f"Full report assembled: {report_id}")
        return md_content
    
    @classmethod
    def _post_process_report(cls, content: str, outline: ReportOutline) -> str:
        """
        Post-process report content.

        1. Remove duplicate headings
        2. Keep the report title (`#`) and section titles (`##`), while converting lower-level headings
        3. Clean up extra blank lines and separators
        
        Args:
            content: Original report content
            outline: Report outline
            
        Returns:
            Processed content
        """
        import re
        
        lines = content.split('\n')
        processed_lines = []
        prev_was_heading = False
        
        # Collect all section titles from the outline.
        section_titles = set()
        for section in outline.sections:
            section_titles.add(section.title)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            # Check whether the line is a heading.
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', stripped)
            
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                # Check for duplicate headings within the previous five processed lines.
                is_duplicate = False
                for j in range(max(0, len(processed_lines) - 5), len(processed_lines)):
                    prev_line = processed_lines[j].strip()
                    prev_match = re.match(r'^(#{1,6})\s+(.+)$', prev_line)
                    if prev_match:
                        prev_title = prev_match.group(2).strip()
                        if prev_title == title:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    # Skip duplicate headings and the blank lines immediately after them.
                    i += 1
                    while i < len(lines) and lines[i].strip() == '':
                        i += 1
                    continue
                
                # Heading level handling:
                # - # (level=1): keep only the main report title
                # - ## (level=2): keep section titles
                # - ### and below (level>=3): convert to bold text
                
                if level == 1:
                    if title == outline.title:
                        # Keep the main report title.
                        processed_lines.append(line)
                        prev_was_heading = True
                    elif title in section_titles:
                        # A section title incorrectly used `#`, so normalize it to `##`.
                        processed_lines.append(f"## {title}")
                        prev_was_heading = True
                    else:
                        # Convert other level-1 headings to bold text.
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                elif level == 2:
                    if title in section_titles or title == outline.title:
                        # Keep valid section headings.
                        processed_lines.append(line)
                        prev_was_heading = True
                    else:
                        # Convert non-section level-2 headings to bold text.
                        processed_lines.append(f"**{title}**")
                        processed_lines.append("")
                        prev_was_heading = False
                else:
                    # Convert level-3 and lower headings to bold text.
                    processed_lines.append(f"**{title}**")
                    processed_lines.append("")
                    prev_was_heading = False
                
                i += 1
                continue
            
            elif stripped == '---' and prev_was_heading:
                # Skip a separator that appears immediately after a heading.
                i += 1
                continue
            
            elif stripped == '' and prev_was_heading:
                # Keep only one blank line after a heading.
                if processed_lines and processed_lines[-1].strip() != '':
                    processed_lines.append(line)
                prev_was_heading = False
            
            else:
                processed_lines.append(line)
                prev_was_heading = False
            
            i += 1
        
        # Collapse repeated blank lines and keep at most two in a row.
        result_lines = []
        empty_count = 0
        for line in processed_lines:
            if line.strip() == '':
                empty_count += 1
                if empty_count <= 2:
                    result_lines.append(line)
            else:
                empty_count = 0
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @classmethod
    def save_report(cls, report: Report) -> None:
        """Save report metadata and the full report."""
        cls._ensure_report_folder(report.report_id)
        
        # Save metadata JSON.
        with open(cls._get_report_path(report.report_id), 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        
        # Save the outline.
        if report.outline:
            cls.save_outline(report.report_id, report.outline)
        
        # Save the full Markdown report.
        if report.markdown_content:
            with open(cls._get_report_markdown_path(report.report_id), 'w', encoding='utf-8') as f:
                f.write(report.markdown_content)
        
        logger.info(f"Report saved: {report.report_id}")
    
    @classmethod
    def get_report(cls, report_id: str) -> Optional[Report]:
        """Get a report."""
        path = cls._get_report_path(report_id)
        
        if not os.path.exists(path):
            # Backward compatibility: check for legacy files stored directly under reports/.
            old_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
            if os.path.exists(old_path):
                path = old_path
            else:
                return None
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Rebuild the Report object.
        outline = None
        if data.get('outline'):
            outline_data = data['outline']
            sections = []
            for s in outline_data.get('sections', []):
                sections.append(ReportSection(
                    title=s['title'],
                    content=s.get('content', '')
                ))
            outline = ReportOutline(
                title=outline_data['title'],
                summary=outline_data['summary'],
                sections=sections
            )
        
        # If markdown_content is empty, try reading it from full_report.md.
        markdown_content = data.get('markdown_content', '')
        if not markdown_content:
            full_report_path = cls._get_report_markdown_path(report_id)
            if os.path.exists(full_report_path):
                with open(full_report_path, 'r', encoding='utf-8') as f:
                    markdown_content = f.read()
        
        return Report(
            report_id=data['report_id'],
            simulation_id=data['simulation_id'],
            graph_id=data['graph_id'],
            base_graph_id=data.get('base_graph_id'),
            runtime_graph_id=data.get('runtime_graph_id'),
            graph_ids=data.get('graph_ids') or [],
            simulation_requirement=data['simulation_requirement'],
            status=ReportStatus(data['status']),
            outline=outline,
            markdown_content=markdown_content,
            created_at=data.get('created_at', ''),
            completed_at=data.get('completed_at', ''),
            error=data.get('error'),
            ensemble_id=data.get('ensemble_id'),
            cluster_id=data.get('cluster_id'),
            run_id=data.get('run_id'),
            probabilistic_context=data.get('probabilistic_context'),
        )
    
    @classmethod
    def get_report_by_simulation(cls, simulation_id: str) -> Optional[Report]:
        """Get a report by simulation ID."""
        reports = cls.list_reports(simulation_id=simulation_id, limit=1)
        return reports[0] if reports else None

    @classmethod
    def get_report_for_scope(
        cls,
        simulation_id: str,
        *,
        ensemble_id: Optional[str] = None,
        cluster_id: Optional[str] = None,
        run_id: Optional[str] = None,
        legacy_only: bool = False,
    ) -> Optional[Report]:
        """Get the newest report that matches one exact probabilistic or legacy scope."""
        reports = cls.list_reports(simulation_id=simulation_id, limit=200)

        if legacy_only:
            reports = [
                report for report in reports
                if not report.ensemble_id and not report.cluster_id and not report.run_id
            ]
            return reports[0] if reports else None

        if ensemble_id is not None:
            reports = [
                report for report in reports
                if (
                    report.ensemble_id == ensemble_id
                    and report.cluster_id == cluster_id
                    and report.run_id == run_id
                )
            ]
            return reports[0] if reports else None

        return cls.get_report_by_simulation(simulation_id)
    
    @classmethod
    def list_reports(cls, simulation_id: Optional[str] = None, limit: int = 50) -> List[Report]:
        """List reports."""
        cls._ensure_reports_dir()
        
        reports = []
        for item in os.listdir(cls.REPORTS_DIR):
            item_path = os.path.join(cls.REPORTS_DIR, item)
            # New format: folder.
            if os.path.isdir(item_path):
                report = cls.get_report(item)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
            # Backward-compatible legacy format: JSON file.
            elif item.endswith('.json'):
                report_id = item[:-5]
                report = cls.get_report(report_id)
                if report:
                    if simulation_id is None or report.simulation_id == simulation_id:
                        reports.append(report)
        
        # Sort by creation time in descending order.
        reports.sort(key=lambda r: r.created_at, reverse=True)
        
        return reports[:limit]
    
    @classmethod
    def delete_report(cls, report_id: str) -> bool:
        """Delete a report, including its folder."""
        import shutil
        
        folder_path = cls._get_report_folder(report_id)
        
        # New format: delete the entire folder.
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            shutil.rmtree(folder_path)
            logger.info(f"Report folder deleted: {report_id}")
            return True
        
        # Backward-compatible legacy format: delete standalone files.
        deleted = False
        old_json_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.json")
        old_md_path = os.path.join(cls.REPORTS_DIR, f"{report_id}.md")
        
        if os.path.exists(old_json_path):
            os.remove(old_json_path)
            deleted = True
        if os.path.exists(old_md_path):
            os.remove(old_md_path)
            deleted = True
        
        return deleted
