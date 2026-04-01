"""
Action logger utilities.
Used to record each agent action during OASIS simulations for backend monitoring.

Log layout:
    sim_xxx/
      twitter/
        actions.jsonl        # Twitter action log
      reddit/
        actions.jsonl        # Reddit action log
      simulation.log         # Main simulation process log
      run_state.json         # Runtime state (for API queries)
"""

import json
import os
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

try:  # pragma: no cover - import availability depends on script launch context
    from app.services.runtime_graph_state_store import RuntimeGraphStateStore
except Exception:  # pragma: no cover - keep logging usable even without backend imports
    RuntimeGraphStateStore = None


class PlatformActionLogger:
    """Action logger for a single platform."""
    
    def __init__(self, platform: str, base_dir: str):
        """
        Initialize the logger.

        Args:
            platform: Platform name (twitter/reddit)
            base_dir: Base path for the simulation directory
        """
        self.platform = platform
        self.base_dir = base_dir
        self.log_dir = os.path.join(base_dir, platform)
        self.log_path = os.path.join(self.log_dir, "actions.jsonl")
        self.runtime_state_store = (
            RuntimeGraphStateStore(base_dir)
            if RuntimeGraphStateStore is not None
            else None
        )
        self._ensure_dir()
    
    def _ensure_dir(self):
        """Ensure the log directory exists."""
        os.makedirs(self.log_dir, exist_ok=True)
    
    def log_action(
        self,
        round_num: int,
        agent_id: int,
        agent_name: str,
        action_type: str,
        action_args: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        success: bool = True
    ):
        """Record a single action."""
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "action_args": action_args or {},
            "result": result,
            "success": success,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        self._record_structured_action(entry)
    
    def log_round_start(self, round_num: int, simulated_hour: int):
        """Record the start of a round."""
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "event_type": "round_start",
            "simulated_hour": simulated_hour,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        self._record_round_state(
            round_num=round_num,
            timestamp=entry["timestamp"],
            phase="round_start",
            simulated_hour=simulated_hour,
        )
    
    def log_round_end(self, round_num: int, actions_count: int):
        """Record the end of a round."""
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "event_type": "round_end",
            "actions_count": actions_count,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        self._record_round_state(
            round_num=round_num,
            timestamp=entry["timestamp"],
            phase="round_end",
            total_actions=actions_count,
        )
    
    def log_simulation_start(self, config: Dict[str, Any]):
        """Record the start of a simulation."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "simulation_start",
            "platform": self.platform,
            "total_rounds": config.get("time_config", {}).get("total_simulation_hours", 72) * 2,
            "agents_count": len(config.get("agent_configs", [])),
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        self._record_round_state(
            round_num=0,
            timestamp=entry["timestamp"],
            phase="simulation_start",
            total_rounds=entry["total_rounds"],
            agents_count=entry["agents_count"],
        )
    
    def log_simulation_end(self, total_rounds: int, total_actions: int):
        """Record the end of a simulation."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "simulation_end",
            "platform": self.platform,
            "total_rounds": total_rounds,
            "total_actions": total_actions,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        self._record_round_state(
            round_num=total_rounds,
            timestamp=entry["timestamp"],
            phase="simulation_end",
            total_rounds=total_rounds,
            total_actions=total_actions,
        )

    def log_event(
        self,
        round_num: int,
        event_name: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Persist an explicit structured runtime event without affecting action logs."""
        if self.runtime_state_store and self.runtime_state_store.exists():
            self.runtime_state_store.record_event(
                platform=self.platform,
                round_num=round_num,
                event_name=event_name,
                details=details or {},
            )

    def log_intervention(
        self,
        round_num: int,
        intervention_name: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Persist an explicit structured runtime intervention."""
        if self.runtime_state_store and self.runtime_state_store.exists():
            self.runtime_state_store.record_intervention(
                platform=self.platform,
                round_num=round_num,
                intervention_name=intervention_name,
                details=details or {},
            )

    def _record_structured_action(self, entry: Dict[str, Any]) -> None:
        if self.runtime_state_store and self.runtime_state_store.exists():
            self.runtime_state_store.record_action(
                platform=self.platform,
                round_num=entry.get("round", 0),
                agent_id=entry.get("agent_id", 0),
                agent_name=entry.get("agent_name", ""),
                action_type=entry.get("action_type", ""),
                action_args=entry.get("action_args", {}),
                result=entry.get("result"),
                success=entry.get("success", True),
                timestamp=entry.get("timestamp"),
            )

    def _record_round_state(
        self,
        *,
        round_num: int,
        timestamp: str,
        phase: str,
        simulated_hour: Optional[int] = None,
        total_rounds: Optional[int] = None,
        total_actions: Optional[int] = None,
        agents_count: Optional[int] = None,
    ) -> None:
        if self.runtime_state_store and self.runtime_state_store.exists():
            self.runtime_state_store.record_round_state(
                platform=self.platform,
                round_num=round_num,
                phase=phase,
                timestamp=timestamp,
                simulated_hour=simulated_hour,
                total_rounds=total_rounds,
                total_actions=total_actions,
                agents_count=agents_count,
            )


class SimulationLogManager:
    """
    Simulation log manager.
    Manages all simulation log files and keeps them separated by platform.
    """
    
    def __init__(self, simulation_dir: str):
        """
        Initialize the log manager.

        Args:
            simulation_dir: Path to the simulation directory
        """
        self.simulation_dir = simulation_dir
        self.twitter_logger: Optional[PlatformActionLogger] = None
        self.reddit_logger: Optional[PlatformActionLogger] = None
        self._main_logger: Optional[logging.Logger] = None
        
        # Set up the main log
        self._setup_main_logger()
    
    def _setup_main_logger(self):
        """Configure the main simulation logger."""
        log_path = os.path.join(self.simulation_dir, "simulation.log")
        
        # Create the logger
        self._main_logger = logging.getLogger(f"simulation.{os.path.basename(self.simulation_dir)}")
        self._main_logger.setLevel(logging.INFO)
        self._main_logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(log_path, encoding='utf-8', mode='w')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self._main_logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        self._main_logger.addHandler(console_handler)
        
        self._main_logger.propagate = False
    
    def get_twitter_logger(self) -> PlatformActionLogger:
        """Get the Twitter platform logger."""
        if self.twitter_logger is None:
            self.twitter_logger = PlatformActionLogger("twitter", self.simulation_dir)
        return self.twitter_logger
    
    def get_reddit_logger(self) -> PlatformActionLogger:
        """Get the Reddit platform logger."""
        if self.reddit_logger is None:
            self.reddit_logger = PlatformActionLogger("reddit", self.simulation_dir)
        return self.reddit_logger
    
    def log(self, message: str, level: str = "info"):
        """Write to the main log."""
        if self._main_logger:
            getattr(self._main_logger, level.lower(), self._main_logger.info)(message)
    
    def info(self, message: str):
        self.log(message, "info")
    
    def warning(self, message: str):
        self.log(message, "warning")
    
    def error(self, message: str):
        self.log(message, "error")
    
    def debug(self, message: str):
        self.log(message, "debug")


FILTERED_ACTIONS = {'refresh', 'sign_up'}

ACTION_TYPE_MAP = {
    'create_post': 'CREATE_POST',
    'like_post': 'LIKE_POST',
    'dislike_post': 'DISLIKE_POST',
    'repost': 'REPOST',
    'quote_post': 'QUOTE_POST',
    'follow': 'FOLLOW',
    'mute': 'MUTE',
    'create_comment': 'CREATE_COMMENT',
    'like_comment': 'LIKE_COMMENT',
    'dislike_comment': 'DISLIKE_COMMENT',
    'search_posts': 'SEARCH_POSTS',
    'search_user': 'SEARCH_USER',
    'trend': 'TREND',
    'do_nothing': 'DO_NOTHING',
    'interview': 'INTERVIEW',
}


def get_agent_names_from_config(config: Dict[str, Any]) -> Dict[int, str]:
    """Resolve `agent_id -> entity_name` from one prepared simulation config."""
    agent_names = {}
    for agent_config in config.get("agent_configs", []):
        agent_id = agent_config.get("agent_id")
        entity_name = agent_config.get("entity_name", f"Agent_{agent_id}")
        if agent_id is not None:
            agent_names[agent_id] = entity_name
    return agent_names


def fetch_new_actions_from_db(
    db_path: str,
    last_rowid: int,
    agent_names: Dict[int, str],
) -> Tuple[List[Dict[str, Any]], int]:
    """Read newly appended OASIS actions and enrich them with lightweight context."""
    actions = []
    new_last_rowid = last_rowid

    if not os.path.exists(db_path):
        return actions, new_last_rowid

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT rowid, user_id, action, info
            FROM trace
            WHERE rowid > ?
            ORDER BY rowid ASC
            """,
            (last_rowid,),
        )

        for rowid, user_id, action, info_json in cursor.fetchall():
            new_last_rowid = rowid
            if action in FILTERED_ACTIONS:
                continue

            try:
                action_args = json.loads(info_json) if info_json else {}
            except json.JSONDecodeError:
                action_args = {}

            simplified_args = {}
            for key in (
                'content',
                'post_id',
                'comment_id',
                'quoted_id',
                'new_post_id',
                'follow_id',
                'query',
                'like_id',
                'dislike_id',
                'user_id',
                'target_id',
            ):
                if key in action_args:
                    simplified_args[key] = action_args[key]

            action_type = ACTION_TYPE_MAP.get(action, action.upper())
            _enrich_action_context(cursor, action_type, simplified_args, agent_names)
            actions.append(
                {
                    'agent_id': user_id,
                    'agent_name': agent_names.get(user_id, f'Agent_{user_id}'),
                    'action_type': action_type,
                    'action_args': simplified_args,
                }
            )

        conn.close()
    except Exception:
        return actions, new_last_rowid

    return actions, new_last_rowid


def _enrich_action_context(
    cursor,
    action_type: str,
    action_args: Dict[str, Any],
    agent_names: Dict[int, str],
) -> None:
    try:
        if action_type in ('LIKE_POST', 'DISLIKE_POST'):
            post_info = _get_post_info(cursor, action_args.get('post_id'), agent_names)
            if post_info:
                action_args['post_content'] = post_info.get('content', '')
                action_args['post_author_name'] = post_info.get('author_name', '')
        elif action_type == 'REPOST':
            new_post_id = action_args.get('new_post_id')
            if new_post_id:
                cursor.execute(
                    """
                    SELECT original_post_id FROM post WHERE post_id = ?
                    """,
                    (new_post_id,),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    original_info = _get_post_info(cursor, row[0], agent_names)
                    if original_info:
                        action_args['original_content'] = original_info.get('content', '')
                        action_args['original_author_name'] = original_info.get('author_name', '')
        elif action_type == 'QUOTE_POST':
            original_info = _get_post_info(cursor, action_args.get('quoted_id'), agent_names)
            if original_info:
                action_args['original_content'] = original_info.get('content', '')
                action_args['original_author_name'] = original_info.get('author_name', '')
            new_post_id = action_args.get('new_post_id')
            if new_post_id:
                cursor.execute(
                    """
                    SELECT quote_content FROM post WHERE post_id = ?
                    """,
                    (new_post_id,),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    action_args['quote_content'] = row[0]
        elif action_type == 'FOLLOW':
            follow_id = action_args.get('follow_id')
            if follow_id:
                cursor.execute(
                    """
                    SELECT followee_id FROM follow WHERE follow_id = ?
                    """,
                    (follow_id,),
                )
                row = cursor.fetchone()
                if row:
                    action_args['target_user_name'] = _get_user_name(cursor, row[0], agent_names)
        elif action_type == 'MUTE':
            target_id = action_args.get('user_id') or action_args.get('target_id')
            if target_id:
                action_args['target_user_name'] = _get_user_name(cursor, target_id, agent_names)
        elif action_type in ('LIKE_COMMENT', 'DISLIKE_COMMENT'):
            comment_info = _get_comment_info(cursor, action_args.get('comment_id'), agent_names)
            if comment_info:
                action_args['comment_content'] = comment_info.get('content', '')
                action_args['comment_author_name'] = comment_info.get('author_name', '')
        elif action_type == 'CREATE_COMMENT':
            post_info = _get_post_info(cursor, action_args.get('post_id'), agent_names)
            if post_info:
                action_args['post_content'] = post_info.get('content', '')
                action_args['post_author_name'] = post_info.get('author_name', '')
    except Exception:
        return


def _get_post_info(
    cursor,
    post_id: Optional[Any],
    agent_names: Dict[int, str],
) -> Optional[Dict[str, Any]]:
    if not post_id:
        return None
    cursor.execute(
        """
        SELECT content, user_id FROM post WHERE post_id = ?
        """,
        (post_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    content, author_id = row
    return {
        "content": content or "",
        "author_name": _get_user_name(cursor, author_id, agent_names),
    }


def _get_comment_info(
    cursor,
    comment_id: Optional[Any],
    agent_names: Dict[int, str],
) -> Optional[Dict[str, Any]]:
    if not comment_id:
        return None
    cursor.execute(
        """
        SELECT content, user_id FROM comment WHERE comment_id = ?
        """,
        (comment_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    content, author_id = row
    return {
        "content": content or "",
        "author_name": _get_user_name(cursor, author_id, agent_names),
    }


def _get_user_name(
    cursor,
    user_id: Optional[Any],
    agent_names: Dict[int, str],
) -> str:
    if user_id is None:
        return ""
    if user_id in agent_names:
        return agent_names[user_id]
    cursor.execute(
        """
        SELECT username FROM user WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    return row[0] if row and row[0] else f"Agent_{user_id}"


# ============ Backward-compatible interface ============

class ActionLogger:
    """
    Action logger (legacy interface).
    Prefer `SimulationLogManager` for new code.
    """
    
    def __init__(self, log_path: str):
        self.log_path = log_path
        self._ensure_dir()
    
    def _ensure_dir(self):
        log_dir = os.path.dirname(self.log_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    def log_action(
        self,
        round_num: int,
        platform: str,
        agent_id: int,
        agent_name: str,
        action_type: str,
        action_args: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        success: bool = True
    ):
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "action_type": action_type,
            "action_args": action_args or {},
            "result": result,
            "success": success,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_round_start(self, round_num: int, simulated_hour: int, platform: str):
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "event_type": "round_start",
            "simulated_hour": simulated_hour,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_round_end(self, round_num: int, actions_count: int, platform: str):
        entry = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "event_type": "round_end",
            "actions_count": actions_count,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_simulation_start(self, platform: str, config: Dict[str, Any]):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "event_type": "simulation_start",
            "total_rounds": config.get("time_config", {}).get("total_simulation_hours", 72) * 2,
            "agents_count": len(config.get("agent_configs", [])),
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    def log_simulation_end(self, platform: str, total_rounds: int, total_actions: int):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "event_type": "simulation_end",
            "total_rounds": total_rounds,
            "total_actions": total_actions,
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# Global logger instance (legacy interface)
_global_logger: Optional[ActionLogger] = None


def get_logger(log_path: Optional[str] = None) -> ActionLogger:
    """Get the global logger instance (legacy interface)."""
    global _global_logger
    
    if log_path:
        _global_logger = ActionLogger(log_path)
    
    if _global_logger is None:
        _global_logger = ActionLogger("actions.jsonl")
    
    return _global_logger
