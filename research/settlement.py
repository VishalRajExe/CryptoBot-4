"""
Settlement engine for post-hoc decision scoring.
Adapted from TradingAgents' settlement system.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from cryptobot.research.memory import TradingMemoryLog
from cryptobot.data.fetcher import get_fetcher
from cryptobot.data.models import Symbol, MarketType
from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


class SettlementEngine:
    """
    Settles past decisions with realized outcomes.

    Flow:
    1. Find unresolved decisions from memory log
    2. For each, fetch price data at resolution time
    3. Calculate realized PnL and alpha vs benchmark
    4. Generate LLM reflection on what worked/didn't
    5. Update memory log with outcome
    """

    def __init__(
        self,
        memory_log: TradingMemoryLog | None = None,
        benchmark_symbol: str = "BTC/USDT:binance:linear",
        holding_period_days: int = 7,
    ):
        self.memory_log = memory_log or TradingMemoryLog()
        self.benchmark_symbol = Symbol.from_unified(benchmark_symbol)
        self.holding_period_days = holding_period_days
        self.fetcher = None

    async def _get_fetcher(self):
        if self.fetcher is None:
            self.fetcher = await get_fetcher()
        return self.fetcher

    async def settle_pending(self, as_of: datetime | None = None) -> list[dict[str, Any]]:
        """
        Settle all pending decisions.

        Args:
            as_of: Settlement as-of date (default: now)

        Returns:
            List of settled decisions with outcomes
        """
        as_of = as_of or datetime.utcnow()
        fetcher = await self._get_fetcher()

        unresolved = self.memory_log.get_unresolved(before_date=as_of.strftime("%Y-%m-%d"))
        settled = []

        for metadata in unresolved:
            try:
                result = await self._settle_decision(metadata, fetcher, as_of)
                if result:
                    settled.append(result)
            except Exception as e:
                logger.error(f"Settlement error for {metadata.get('symbol')}: {e}")

        return settled

    async def _settle_decision(
        self,
        metadata: dict[str, Any],
        fetcher,
        as_of: datetime,
    ) -> dict[str, Any] | None:
        """Settle a single decision."""
        symbol_str = metadata.get("symbol")
        entry_date_str = metadata.get("date")
        entry_date = datetime.fromisoformat(entry_date_str.replace("Z", "+00:00"))

        # Check if holding period has passed
        resolution_date = entry_date + timedelta(days=self.holding_period_days)
        if resolution_date > as_of:
            return None  # Not yet time to settle

        symbol = Symbol.from_unified(symbol_str)

        # Fetch entry price (at entry date)
        entry_candles = await fetcher.fetch_candles(
            symbol,
            timeframe="1h",
            start=entry_date - timedelta(hours=1),
            end=entry_date + timedelta(hours=1),
            limit=2,
        )
        if not entry_candles:
            logger.warning(f"No entry price data for {symbol_str}")
            return None
        entry_price = float(entry_candles[0].close)

        # Fetch exit price (at resolution date)
        exit_candles = await fetcher.fetch_candles(
            symbol,
            timeframe="1h",
            start=resolution_date - timedelta(hours=1),
            end=resolution_date + timedelta(hours=1),
            limit=2,
        )
        if not exit_candles:
            logger.warning(f"No exit price data for {symbol_str}")
            return None
        exit_price = float(exit_candles[0].close)

        # Fetch benchmark prices
        bench_entry = await fetcher.fetch_candles(
            self.benchmark_symbol,
            timeframe="1h",
            start=entry_date - timedelta(hours=1),
            end=entry_date + timedelta(hours=1),
            limit=2,
        )
        bench_exit = await fetcher.fetch_candles(
            self.benchmark_symbol,
            timeframe="1h",
            start=resolution_date - timedelta(hours=1),
            end=resolution_date + timedelta(hours=1),
            limit=2,
        )

        bench_entry_price = float(bench_entry[0].close) if bench_entry else entry_price
        bench_exit_price = float(bench_exit[0].close) if bench_exit else exit_price

        # Calculate returns
        pnl_pct = (exit_price - entry_price) / entry_price
        bench_return = (bench_exit_price - bench_entry_price) / bench_entry_price
        alpha = pnl_pct - bench_return

        # Determine action from metadata (simplified)
        action = "long"  # Would parse from decision
        if action == "short":
            pnl_pct = -pnl_pct
            alpha = -alpha

        # Generate reflection using LLM
        reflection = await self._generate_reflection(
            symbol_str, entry_date_str, pnl_pct, alpha, bench_return
        )

        # Update memory log
        self.memory_log.mark_resolved(
            symbol=symbol_str,
            date=entry_date_str,
            realized_pnl=pnl_pct,
            alpha=alpha,
            reflection=reflection,
        )

        return {
            "symbol": symbol_str,
            "entry_date": entry_date_str,
            "resolution_date": resolution_date.isoformat(),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "realized_pnl_pct": pnl_pct,
            "benchmark_return_pct": bench_return,
            "alpha_pct": alpha,
            "reflection": reflection,
        }

    async def _generate_reflection(
        self,
        symbol: str,
        entry_date: str,
        pnl_pct: float,
        alpha: float,
        bench_return: float,
    ) -> str:
        """Generate LLM reflection on the trade outcome."""
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage

        llm = ChatOpenAI(model="gpt-4o", temperature=0.3)

        outcome = "profitable" if pnl_pct > 0 else "loss-making"
        alpha_str = "outperformed" if alpha > 0 else "underperformed"

        prompt = f"""Reflect on this completed trade:

Symbol: {symbol}
Entry Date: {entry_date}
Holding Period: {self.holding_period_days} days
Result: {outcome} ({pnl_pct:.2%})
Benchmark Return: {bench_return:.2%}
Alpha: {alpha:.2%} ({alpha_str} benchmark)

Provide a concise paragraph (3-5 sentences) reflecting on:
1. What the original thesis was (based on outcome)
2. What worked or didn't work
3. Whether the risk management was appropriate
4. One key lesson for future similar trades

Be honest and specific. Don't rationalize losses or over-celebrate wins."""

        response = await llm.ainvoke([SystemMessage(content=prompt)])
        return response.content

    def get_pending_settlement(self) -> list[dict[str, Any]]:
        """Get list of decisions pending settlement."""
        return self.memory_log.get_unresolved()

    async def settle_specific(
        self,
        symbol: str,
        entry_date: str,
        as_of: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Settle a specific decision by symbol and date."""
        as_of = as_of or datetime.utcnow()
        fetcher = await self._get_fetcher()

        metadata = {
            "symbol": symbol,
            "date": entry_date,
        }

        return await self._settle_decision(metadata, fetcher, as_of)

    def get_settlement_stats(self) -> dict[str, Any]:
        """Get statistics on settled decisions."""
        content = self.memory_log.log_path.read_text()

        total = 0
        profitable = 0
        total_pnl = 0.0
        total_alpha = 0.0

        entries = content.split("<!-- PIT_METADATA")[1:]
        for entry in entries:
            lines = entry.split("\n")
            metadata = {}
            for line in lines[:10]:
                if ":" in line and not line.startswith("---"):
                    key, val = line.split(":", 1)
                    metadata[key.strip()] = val.strip()

            if metadata.get("resolved") != "PENDING":
                total += 1
                pnl = float(metadata.get("realized_pnl", 0))
                alpha = float(metadata.get("alpha", 0))
                total_pnl += pnl
                total_alpha += alpha
                if pnl > 0:
                    profitable += 1

        return {
            "total_settled": total,
            "profitable": profitable,
            "win_rate": profitable / total if total else 0,
            "avg_pnl_pct": total_pnl / total if total else 0,
            "avg_alpha_pct": total_alpha / total if total else 0,
        }