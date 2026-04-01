"""Graphiti-backed live runtime graph event updater."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from .graph_backend import GraphBackendSettings, build_graph_backend_service

logger = get_logger("mirofish.runtime_graph_updater")


@dataclass
class RuntimeGraphActivity:
    """One runtime action payload waiting for live graph ingestion."""

    base_graph_id: str
    runtime_graph_id: str
    run_key: str
    platform: str
    agent_id: int
    agent_name: str
    action_type: str
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str
    transition_type: str = ""

    def to_event_payload(self) -> Dict[str, Any]:
        return {
            "artifact_type": "runtime_graph_memory_update",
            "base_graph_id": self.base_graph_id,
            "runtime_graph_id": self.runtime_graph_id,
            "run_key": self.run_key,
            "platform": self.platform,
            "round_num": self.round_num,
            "timestamp": self.timestamp,
            "transition_type": self.transition_type or self._infer_transition_type(),
            "agent": {
                "agent_id": self.agent_id,
                "agent_name": self.agent_name,
            },
            "action": {
                "action_type": self.action_type,
                "action_args": dict(self.action_args),
            },
            "human_readable": self._describe_human_readable(),
            "source_artifact": "runtime_graph_updates.jsonl",
        }

    def _describe_human_readable(self) -> str:
        text = (
            self.action_args.get("content")
            or self.action_args.get("quote_content")
            or self.action_args.get("query")
            or self.action_args.get("post_content")
            or self.action_args.get("comment_content")
        )
        if text:
            return f"{self.agent_name} {self.action_type.lower()} :: {text}"
        return f"{self.agent_name} {self.action_type.lower()}"

    def _infer_transition_type(self) -> str:
        if self.action_type in {"CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"}:
            return "claim"
        if self.action_type in {
            "LIKE_POST",
            "DISLIKE_POST",
            "REPOST",
            "LIKE_COMMENT",
            "DISLIKE_COMMENT",
            "FOLLOW",
            "MUTE",
        }:
            return "belief_update"
        if self.action_type in {"SEARCH_POSTS", "SEARCH_USER", "TREND", "REFRESH"}:
            return "topic_shift"
        return "exposure"


class RuntimeGraphUpdater:
    """Batch runtime action updates into one runtime namespace."""

    SEND_INTERVAL = 0.5
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(
        self,
        *,
        run_key: str,
        base_graph_id: str,
        runtime_graph_id: str,
        run_dir: str,
        graph_backend: Any | None = None,
        settings: GraphBackendSettings | None = None,
    ) -> None:
        self.run_key = run_key
        self.base_graph_id = base_graph_id
        self.runtime_graph_id = runtime_graph_id
        self.run_dir = run_dir
        self.settings = settings or GraphBackendSettings.from_env()
        self.graph_backend = graph_backend or build_graph_backend_service(self.settings)
        self.batch_size = max(1, int(self.settings.runtime_batch_size))

        self._activity_queue: Queue[RuntimeGraphActivity] = Queue()
        self._platform_buffers: Dict[str, List[RuntimeGraphActivity]] = {
            "twitter": [],
            "reddit": [],
        }
        self._buffer_lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        self._total_activities = 0
        self._total_sent = 0
        self._total_items_sent = 0
        self._failed_count = 0
        self._skipped_count = 0

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"RuntimeGraphUpdater-{self.runtime_graph_id[:8]}",
        )
        self._worker_thread.start()

    def stop(self) -> None:
        self._running = False
        self._flush_remaining()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)

    def add_activity(self, activity: RuntimeGraphActivity) -> None:
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return
        self._activity_queue.put(activity)
        self._total_activities += 1

    def add_activity_from_dict(self, data: Dict[str, Any], platform: str) -> None:
        if "event_type" in data:
            return
        activity = RuntimeGraphActivity(
            base_graph_id=self.base_graph_id,
            runtime_graph_id=self.runtime_graph_id,
            run_key=self.run_key,
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=dict(data.get("action_args", {})),
            round_num=int(data.get("round", 0) or 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )
        self.add_activity(activity)

    def get_stats(self) -> Dict[str, Any]:
        with self._buffer_lock:
            buffer_sizes = {platform: len(items) for platform, items in self._platform_buffers.items()}
        return {
            "base_graph_id": self.base_graph_id,
            "runtime_graph_id": self.runtime_graph_id,
            "batch_size": self.batch_size,
            "total_activities": self._total_activities,
            "batches_sent": self._total_sent,
            "items_sent": self._total_items_sent,
            "failed_count": self._failed_count,
            "skipped_count": self._skipped_count,
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,
            "running": self._running,
        }

    def _worker_loop(self) -> None:
        while self._running or not self._activity_queue.empty():
            try:
                try:
                    activity = self._activity_queue.get(timeout=1)
                except Empty:
                    continue

                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
                    if len(self._platform_buffers[platform]) < self.batch_size:
                        continue
                    batch = self._platform_buffers[platform][: self.batch_size]
                    self._platform_buffers[platform] = self._platform_buffers[platform][self.batch_size :]

                self._send_batch_activities(batch, platform)
                time.sleep(self.SEND_INTERVAL)
            except Exception as exc:
                logger.error("Runtime graph updater loop exception: %s", exc)
                time.sleep(1)

    def _send_batch_activities(
        self,
        activities: List[RuntimeGraphActivity],
        platform: str,
    ) -> None:
        if not activities:
            return

        events = [activity.to_event_payload() for activity in activities]
        for attempt in range(self.MAX_RETRIES):
            try:
                self.graph_backend.append_runtime_events(
                    self.runtime_graph_id,
                    events,
                    batch_size=self.batch_size,
                )
                self._total_sent += 1
                self._total_items_sent += len(events)
                logger.info(
                    "Sent %s runtime events to namespace %s for %s",
                    len(events),
                    self.runtime_graph_id,
                    platform,
                )
                return
            except Exception as exc:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        "Failed runtime event batch %s/%s for %s: %s",
                        attempt + 1,
                        self.MAX_RETRIES,
                        self.runtime_graph_id,
                        exc,
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                logger.error(
                    "Failed runtime event batch after %s retries for %s: %s",
                    self.MAX_RETRIES,
                    self.runtime_graph_id,
                    exc,
                )
                self._failed_count += 1

    def _flush_remaining(self) -> None:
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
            except Empty:
                break
            platform = activity.platform.lower()
            with self._buffer_lock:
                if platform not in self._platform_buffers:
                    self._platform_buffers[platform] = []
                self._platform_buffers[platform].append(activity)

        with self._buffer_lock:
            pending_batches = {
                platform: list(batch)
                for platform, batch in self._platform_buffers.items()
                if batch
            }
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []

        for platform, batch in pending_batches.items():
            self._send_batch_activities(batch, platform)


class RuntimeGraphUpdateManager:
    """Manage one live runtime graph updater per running simulation scope."""

    _updaters: Dict[str, RuntimeGraphUpdater] = {}
    _lock = threading.Lock()
    _stop_all_done = False

    @classmethod
    def create_updater(
        cls,
        run_key: str,
        base_graph_id: str,
        runtime_graph_id: str,
        run_dir: str,
        *,
        graph_backend: Any | None = None,
        settings: GraphBackendSettings | None = None,
    ) -> RuntimeGraphUpdater:
        with cls._lock:
            cls._stop_all_done = False
            if run_key in cls._updaters:
                cls._updaters[run_key].stop()
            updater = RuntimeGraphUpdater(
                run_key=run_key,
                base_graph_id=base_graph_id,
                runtime_graph_id=runtime_graph_id,
                run_dir=run_dir,
                graph_backend=graph_backend,
                settings=settings,
            )
            updater.start()
            cls._updaters[run_key] = updater
            return updater

    @classmethod
    def get_updater(cls, run_key: str) -> Optional[RuntimeGraphUpdater]:
        return cls._updaters.get(run_key)

    @classmethod
    def stop_updater(cls, run_key: str) -> None:
        with cls._lock:
            updater = cls._updaters.pop(run_key, None)
        if updater is not None:
            updater.stop()

    @classmethod
    def stop_all(cls) -> None:
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        with cls._lock:
            updaters = list(cls._updaters.items())
            cls._updaters.clear()
        for _run_key, updater in updaters:
            try:
                updater.stop()
            except Exception as exc:
                logger.error("Failed to stop runtime graph updater: %s", exc)

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        return {
            run_key: updater.get_stats()
            for run_key, updater in cls._updaters.items()
        }
