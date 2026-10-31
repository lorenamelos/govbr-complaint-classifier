"""Write one collection run to data/raw/<run_id>/: Parquet parts, resume state, metadata.

Layout of a run directory:

- `part-00001.parquet`, ...: rows exactly as the collector returned them, author fields included.
  Raw stays on this machine (data/README.md).
- `state.json`: the token to resume from and the progress counters, rewritten at every checkpoint.
- `metadata.json`: parameters, versions, timing, stop reason, review date window and an app
  snapshot. Its `status` is `in_progress` until the run ends, so an interrupted run can never be
  mistaken for a finished one; only `stop_reason == "end_of_history"` means complete history.
"""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from govbr_classifier.data.collect import CollectionState, Row


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _utc(epoch: int | None) -> str | None:
    return None if epoch is None else datetime.fromtimestamp(epoch, UTC).isoformat()


class RawRun:
    """One collection run on disk."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.metadata_path = run_dir / "metadata.json"
        self.state_path = run_dir / "state.json"

    @classmethod
    def create(
        cls, root: Path, parameters: dict[str, Any], environment: dict[str, Any]
    ) -> "RawRun":
        """Start a new run directory named by its UTC start time."""
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run = cls(root / run_id)
        run.run_dir.mkdir(parents=True, exist_ok=False)
        run._write(
            run.metadata_path,
            {
                "run_id": run_id,
                "status": "in_progress",
                "started_at": _now(),
                "parameters": parameters,
                "environment": environment,
                "sessions": [],
            },
        )
        return run

    def resume_point(self) -> tuple[str | None, CollectionState]:
        """Return the token and counters a resumed run continues from."""
        saved = json.loads(self.state_path.read_text())
        state = CollectionState(**saved["state"])
        return saved["token"], state

    def checkpoint(self, rows: list[Row], token: str | None, state: CollectionState) -> None:
        """Write the rows as the next part, then the state to resume from."""
        if rows:
            index = len(list(self.run_dir.glob("part-*.parquet"))) + 1
            pd.DataFrame(rows).to_parquet(self.run_dir / f"part-{index:05d}.parquet", index=False)
        self._write(self.state_path, {"token": token, "state": asdict(state), "saved_at": _now()})

    def finish(self, state: CollectionState, session: dict[str, Any]) -> dict[str, Any]:
        """Record how this session ended and summarize every part written so far."""
        metadata = json.loads(self.metadata_path.read_text())
        metadata["sessions"].append(
            session | {"ended_at": _now(), "stop_reason": state.stop_reason}
        )
        frame = self.load()
        epochs = frame["at_epoch"].dropna() if "at_epoch" in frame else pd.Series(dtype=float)
        seconds = state.page_seconds
        metadata.update(
            {
                "status": "complete" if state.stop_reason == "end_of_history" else "stopped",
                "stop_reason": state.stop_reason,
                "last_error": state.last_error,
                "pages": state.pages,
                "reviews_fetched": state.reviews,
                "rows_on_disk": len(frame),
                "retries": state.retries,
                "seconds_per_page": {
                    "median": float(pd.Series(seconds).median()) if seconds else None,
                    "p90": float(pd.Series(seconds).quantile(0.9)) if seconds else None,
                },
                "review_window_utc": {
                    "oldest": _utc(int(epochs.min())) if len(epochs) else None,
                    "newest": _utc(int(epochs.max())) if len(epochs) else None,
                },
            }
        )
        self._write(self.metadata_path, metadata)
        return metadata

    def load(self) -> pd.DataFrame:
        """All rows of this run, in part order."""
        parts = sorted(self.run_dir.glob("part-*.parquet"))
        if not parts:
            return pd.DataFrame()
        return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        temporary.replace(path)
