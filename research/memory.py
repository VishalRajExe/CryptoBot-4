"""
Trading memory log with atomic writes and settlement.
Adapted from TradingAgents' TradingMemoryLog and settlement system.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


class TradingMemoryLog:
    """
    Append-only markdown memory log with atomic writes.

    Features:
    - Atomic writes via temp file + os.replace
    - Point-in-time filtering via resolved: date tags
    - Structured decision entries
    - Automatic rotation
    """

    def __init__(self, log_path: str | Path | None = None):
        self.log_path = Path(log_path or settings.data_dir / "memory" / "trading_memory.md")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._ensure_log_exists()

    def _ensure_log_exists(self) -> None:
        """Create log file with header if it doesn't exist."""
        if not self.log_path.exists():
            header = f"""# Trading Memory Log
Created: {datetime.utcnow().isoformat()}
Format: Each decision entry is a markdown section with PIT metadata.
Point-in-Time: Use `resolved: YYYY-MM-DD` to mark when outcome was known.
---
"""
            self.log_path.write_text(header)

    async def append_decision(
        self,
        symbol: str,
        date: str,
        decision: dict[str, Any],
        analyses: dict[str, Any],
        debate_history: list[dict[str, Any]] | None = None,
        risk_debate: list[dict[str, Any]] | None = None,
    ) -> None:
        """Append a decision to the memory log atomically."""
        async with self._lock:
            entry = self._format_entry(
                symbol=symbol,
                date=date,
                decision=decision,
                analyses=analyses,
                debate_history=debate_history or [],
                risk_debate=risk_debate or [],
            )

            # Atomic write: write to temp file then replace
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=self.log_path.parent,
                delete=False,
                suffix='.md'
            ) as tmp:
                # Read existing content
                existing = self.log_path.read_text() if self.log_path.exists() else ""
                tmp.write(existing + "\n" + entry)
                tmp_path = tmp.name

            try:
                os.replace(tmp_path, self.log_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

    def _format_entry(
        self,
        symbol: str,
        date: str,
        decision: dict[str, Any],
        analyses: dict[str, Any],
        debate_history: list[dict[str, Any]],
        risk_debate: list[dict[str, Any]],
    ) -> str:
        """Format a decision entry as markdown."""
        final_orders = decision.get("final_orders", [])
        orders_str = "\n".join([
            f"- {o['symbol']}: {o['action'].upper()} {o.get('size_pct', 0)*100:.1f}% "
            f"@ {o.get('limit_price', 'market')} SL:{o.get('stop_loss', 'N/A')} "
            f"TP:{o.get('take_profit', 'N/A')}"
            for o in final_orders
        ]) or "No orders"

        analyses_summary = "\n".join([
            f"### {name.replace('_', ' ').title()}\n"
            f"{self._summarize_analysis(data)}"
            for name, data in analyses.items()
            if data and not data.get("error")
        ]) or "No analyses available"

        debate_str = "\n".join([
            f"**{d['role'].title()}**: {d['content'][:200]}..."
            for d in debate_history[-4:]  # Last 2 rounds
        ]) or "No debate recorded"

        risk_str = "\n".join([
            f"**{d['persona'].title()}**: {d['assessment'].get('key_arguments', [])}"
            for d in risk_debate
        ]) or "No risk debate"

        return f"""## Decision: {symbol} | {date} | {datetime.utcnow().isoformat()}

**Final Orders:**
{orders_str}

**Rationale:**
{decision.get('rationale', 'No rationale provided')}

**Portfolio Adjustments:**
{json.dumps(decision.get('portfolio_adjustments', {}), indent=2)}

**Risk Limits OK:** {decision.get('risk_limits_ok', 'Unknown')}

---

### Analyses
{analyses_summary}

---

### Debate History
{debate_str}

---

### Risk Debate
{risk_str}

---

<!-- PIT_METADATA
symbol: {symbol}
date: {date}
entry_date: {datetime.utcnow().isoformat()}
resolved: PENDING
outcome: PENDING
realized_pnl: PENDING
alpha: PENDING
-->
"""

    def _summarize_analysis(self, analysis: dict[str, Any]) -> str:
        """Create brief summary of analysis."""
        if "symbols" in analysis:
            # Multi-symbol analysis
            summaries = []
            for sym, data in analysis["symbols"].items():
                if data.get("signals"):
                    sig = data["signals"][0]
                    summaries.append(f"- {sym}: {sig['direction']} ({sig['type']}) conf={data.get('confidence', 0):.2f}")
            return "\n".join(summaries) if summaries else "No signals"
        return "Analysis completed"

    def get_recent(self, symbol: str, limit: int = 10) -> str:
        """Get recent memory entries for a symbol."""
        content = self.log_path.read_text()
        entries = content.split("## Decision: ")

        symbol_entries = []
        for entry in entries[1:]:  # Skip header
            if entry.startswith(symbol + " |"):
                symbol_entries.append("## Decision: " + entry)
                if len(symbol_entries) >= limit:
                    break

        return "\n\n".join(symbol_entries) if symbol_entries else ""

    def get_all_for_date(self, date: str) -> list[str]:
        """Get all entries for a specific date."""
        content = self.log_path.read_text()
        entries = content.split("## Decision: ")
        date_entries = []

        for entry in entries[1:]:
            if f" | {date} |" in entry.split("\n")[0]:
                date_entries.append("## Decision: " + entry)

        return date_entries

    def get_unresolved(self, before_date: str | None = None) -> list[dict[str, Any]]:
        """Get all unresolved decisions, optionally before a date."""
        content = self.log_path.read_text()
        entries = content.split("<!-- PIT_METADATA")[1:]  # Split by metadata blocks

        unresolved = []
        for entry in entries:
            lines = entry.split("\n")
            metadata = {}
            for line in lines[:10]:
                if ":" in line and not line.startswith("---"):
                    key, val = line.split(":", 1)
                    metadata[key.strip()] = val.strip()

            if metadata.get("resolved") == "PENDING":
                if before_date is None or metadata.get("date", "") <= before_date:
                    unresolved.append(metadata)

        return unresolved

    def mark_resolved(
        self,
        symbol: str,
        date: str,
        realized_pnl: float,
        alpha: float,
        reflection: str,
    ) -> bool:
        """Mark a decision as resolved with outcome (atomic update)."""
        content = self.log_path.read_text()

        # Find and replace the PIT_METADATA block
        lines = content.split("\n")
        in_metadata = False
        found = False
        new_lines = []

        for line in lines:
            if "<!-- PIT_METADATA" in line:
                in_metadata = True
                new_lines.append(line)
                continue

            if in_metadata:
                if "symbol: " in line and line.strip().endswith(symbol):
                    # Check if this is the right entry
                    # We need to look ahead for date
                    pass
                if "resolved: PENDING" in line:
                    line = line.replace("resolved: PENDING", f"resolved: {datetime.utcnow().strftime('%Y-%m-%d')}")
                    found = True
                if "realized_pnl: PENDING" in line:
                    line = line.replace("realized_pnl: PENDING", f"realized_pnl: {realized_pnl:.4f}")
                if "alpha: PENDING" in line:
                    line = line.replace("alpha: PENDING", f"alpha: {alpha:.4f}")
                if "-->" in line:
                    # Add reflection before closing
                    new_lines.append(f"reflection: {reflection}")
                    in_metadata = False

            new_lines.append(line)

        if found:
            # Atomic write
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=self.log_path.parent,
                delete=False,
                suffix='.md'
            ) as tmp:
                tmp.write("\n".join(new_lines))
                tmp_path = tmp.name
            os.replace(tmp_path, self.log_path)
            return True

        return False

    def rotate_log(self, max_size_mb: int = 50) -> None:
        """Rotate log if it exceeds max size."""
        if self.log_path.stat().st_size > max_size_mb * 1024 * 1024:
            archive_path = self.log_path.parent / f"trading_memory_{datetime.utcnow().strftime('%Y%m')}.md"
            self.log_path.rename(archive_path)
            self._ensure_log_exists()
            logger.info(f"Rotated memory log to {archive_path}")