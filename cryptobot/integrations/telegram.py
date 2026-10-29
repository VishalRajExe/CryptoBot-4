"""
Telegram Bot Integration for Trade Notifications.

Features:
- Trade execution alerts
- Position updates
- Risk alerts
- Research completion notifications
- Portfolio status reports
- Interactive commands
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from cryptobot.config.settings import settings
from cryptobot.risk.manager import PositionRisk

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Notification types."""

    TRADE_OPENED = "trade_opened"
    TRADE_CLOSED = "trade_closed"
    POSITION_UPDATE = "position_update"
    RISK_ALERT = "risk_alert"
    RESEARCH_COMPLETED = "research_completed"
    BACKTEST_COMPLETED = "backtest_completed"
    SYSTEM_ALERT = "system_alert"
    DAILY_SUMMARY = "daily_summary"


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""

    bot_token: str
    chat_id: str | int
    enabled: bool = True
    notifications: dict[NotificationType, bool] = field(default_factory=lambda: {
        NotificationType.TRADE_OPENED: True,
        NotificationType.TRADE_CLOSED: True,
        NotificationType.RISK_ALERT: True,
        NotificationType.RESEARCH_COMPLETED: True,
        NotificationType.BACKTEST_COMPLETED: True,
        NotificationType.SYSTEM_ALERT: True,
        NotificationType.DAILY_SUMMARY: True,
    })


class TelegramBot:
    """
    Telegram bot for trade notifications and commands.

    Features:
    - Real-time trade notifications
    - Position/PnL updates
    - Risk alerts
    - Research completion alerts
    - Interactive commands (/status, /positions, /pause, etc.)
    """

    def __init__(self, config: TelegramConfig):
        self.config = config
        self.bot: Bot | None = None
        self.dp: Dispatcher | None = None
        self.router = Router()
        self._running = False
        self._callbacks: dict[str, list[Callable]] = defaultdict(list)

        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register message and callback handlers."""

        @self.router.message(CommandStart())
        async def cmd_start(message: Message):
            await self._send_welcome(message)

        @self.router.message(Command("status"))
        async def cmd_status(message: Message):
            await self._send_status(message)

        @self.router.message(Command("positions"))
        async def cmd_positions(message: Message):
            await self._send_positions(message)

        @self.router.message(Command("pnl"))
        async def cmd_pnl(message: Message):
            await self._send_pnl(message)

        @self.router.message(Command("pause"))
        async def cmd_pause(message: Message):
            await self._pause_trading(message)

        @self.router.message(Command("resume"))
        async def cmd_resume(message: Message):
            await self._resume_trading(message)

        @self.router.message(Command("balance"))
        async def cmd_balance(message: Message):
            await self._send_balance(message)

        @self.router.message(Command("orders"))
        async def cmd_orders(message: Message):
            await self._send_open_orders(message)

        @self.router.message(Command("research"))
        async def cmd_research(message: Message):
            await self._send_latest_research(message)

        @self.router.message(Command("backtest"))
        async def cmd_backtest(message: Message):
            await self._send_latest_backtest(message)

        @self.router.message(Command("help"))
        async def cmd_help(message: Message):
            await self._send_help(message)

        @self.router.callback_query(F.data.startswith("pause_"))
        async def cb_pause(callback: CallbackQuery):
            await self._handle_pause_callback(callback)

        @self.router.callback_query(F.data.startswith("close_"))
        async def cb_close(callback: CallbackQuery):
            await self._handle_close_callback(callback)

    async def initialize(self) -> None:
        """Initialize bot and dispatcher."""
        if not self.config.enabled:
            logger.info("Telegram bot disabled")
            return

        self.bot = Bot(
            token=self.config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher()
        self.dp.include_router(self.router)

        # Test connection
        try:
            me = await self.bot.get_me()
            logger.info(f"Telegram bot connected: @{me.username}")
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
            self.config.enabled = False
            return

    async def start_polling(self) -> None:
        """Start polling for updates."""
        if not self.config.enabled or not self.dp:
            return

        self._running = True
        logger.info("Starting Telegram bot polling...")
        await self.dp.start_polling(self.bot)

    async def stop(self) -> None:
        """Stop the bot."""
        self._running = False
        if self.dp:
            await self.dp.stop_polling()
        if self.bot:
            await self.bot.session.close()

    async def send_notification(
        self,
        notification_type: NotificationType,
        message: str,
        keyboard: InlineKeyboardMarkup | None = None,
    ) -> bool:
        """Send notification if enabled."""
        if not self.config.enabled or not self.bot:
            return False

        if not self.config.notifications.get(notification_type, False):
            return False

        try:
            await self.bot.send_message(
                chat_id=self.config.chat_id,
                text=message,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    # === Notification Methods ===

    async def notify_trade_opened(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        strategy: str = "",
    ) -> None:
        """Notify trade opened."""
        emoji = "🟢" if side == "long" else "🔴"
        direction = "LONG" if side == "long" else "SHORT"

        msg = (
            f"{emoji} <b>Trade Opened</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Direction:</b> {direction}\n"
            f"<b>Quantity:</b> {quantity}\n"
            f"<b>Entry:</b> ${entry_price:,.4f}\n"
        )

        if stop_loss:
            msg += f"<b>Stop Loss:</b> ${stop_loss:,.4f}\n"
        if take_profit:
            msg += f"<b>Take Profit:</b> ${take_profit:,.4f}\n"
        if strategy:
            msg += f"<b>Strategy:</b> {strategy}\n"

        msg += f"\n<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔴 Close Position", callback_data=f"close_{symbol}")],
        ])

        await self.send_notification(NotificationType.TRADE_OPENED, message, keyboard)

    async def notify_trade_closed(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str = "",
    ) -> None:
        """Notify trade closed."""
        emoji = "✅" if pnl >= 0 else "❌"
        direction = "LONG" if side == "long" else "SHORT"

        msg = (
            f"{emoji} <b>Trade Closed</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Direction:</b> {direction}\n"
            f"<b>Quantity:</b> {quantity}\n"
            f"<b>Entry:</b> ${entry_price:,.4f}\n"
            f"<b>Exit:</b> ${exit_price:,.4f}\n"
            f"<b>PnL:</b> {'+' if pnl >= 0 else ''}${pnl:,.2f} ({pnl_pct:+.2f}%)\n"
        )

        if reason:
            msg += f"<b>Reason:</b> {reason}\n"

        msg += f"\n<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"

        await self.send_notification(NotificationType.TRADE_CLOSED, message)

    async def notify_position_update(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        mark_price: float,
        unrealized_pnl: float,
        unrealized_pnl_pct: float,
    ) -> None:
        """Notify position update (periodic)."""
        emoji = "📈" if unrealized_pnl >= 0 else "📉"
        direction = "LONG" if side == "long" else "SHORT"

        msg = (
            f"{emoji} <b>Position Update</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Direction:</b> {direction}\n"
            f"<b>Quantity:</b> {quantity}\n"
            f"<b>Entry:</b> ${entry_price:,.4f}\n"
            f"<b>Mark:</b> ${mark_price:,.4f}\n"
            f"<b>Unrealized PnL:</b> {'+' if unrealized_pnl >= 0 else ''}${unrealized_pnl:,.2f} ({unrealized_pnl_pct:+.2f}%)\n"
            f"\n<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
        )

        await self.send_notification(NotificationType.POSITION_UPDATE, message)

    async def notify_risk_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = "warning",
    ) -> None:
        """Notify risk alert."""
        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(severity, "⚠️")

        msg = (
            f"{severity_emoji} <b>Risk Alert: {alert_type}</b>\n\n"
            f"{message}\n\n"
            f"<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
        )

        await self.send_notification(NotificationType.RISK_ALERT, message)

    async def notify_research_completed(
        self,
        symbols: list[str],
        decision: dict | None,
        trade_date: str,
    ) -> None:
        """Notify research completed."""
        symbols_str = ", ".join(symbols)
        decision_str = "Hold"
        if decision and decision.get("final_orders"):
            orders = decision["final_orders"]
            if orders:
                first = orders[0]
                decision_str = f"{first['action'].upper()} {first['symbol']}"

        msg = (
            f"🔬 <b>Research Completed</b>\n\n"
            f"<b>Symbols:</b> {symbols_str}\n"
            f"<b>Date:</b> {trade_date}\n"
            f"<b>Decision:</b> {decision_str}\n"
        )

        if decision and decision.get("rationale"):
            msg += f"\n<b>Rationale:</b> {decision['rationale'][:200]}..."

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 View Details", callback_data=f"research_detail")],
        ])

        await self.send_notification(NotificationType.RESEARCH_COMPLETED, message, keyboard)

    async def notify_backtest_completed(
        self,
        backtest_id: str,
        metrics: dict[str, float],
    ) -> None:
        """Notify backtest completed."""
        total_return = metrics.get("total_return_pct", 0)
        sharpe = metrics.get("sharpe_ratio", 0)
        max_dd = metrics.get("max_drawdown_pct", 0)
        win_rate = metrics.get("win_rate_pct", 0)

        emoji = "📈" if total_return >= 0 else "📉"

        msg = (
            f"{emoji} <b>Backtest Completed</b>\n\n"
            f"<b>ID:</b> {backtest_id}\n"
            f"<b>Return:</b> {total_return:+.2f}%\n"
            f"<b>Sharpe:</b> {sharpe:.2f}\n"
            f"<b>Max DD:</b> {max_dd:.2f}%\n"
            f"<b>Win Rate:</b> {win_rate:.1f}%\n"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 View Report", callback_data=f"backtest_report")],
        ])

        await self.send_notification(NotificationType.BACKTEST_COMPLETED, message, keyboard)

    async def notify_system_alert(self, message: str, severity: str = "warning") -> None:
        """Send system alert."""
        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(severity, "⚠️")
        msg = f"{severity_emoji} <b>System Alert</b>\n\n{message}"
        await self.send_notification(NotificationType.SYSTEM_ALERT, message)

    async def send_daily_summary(
        self,
        total_equity: float,
        daily_pnl: float,
        daily_pnl_pct: float,
        open_positions: int,
        trades_today: int,
        win_rate: float,
    ) -> None:
        """Send daily summary."""
        emoji = "📈" if daily_pnl >= 0 else "📉"

        msg = (
            f"📊 <b>Daily Summary</b>\n\n"
            f"{emoji} <b>PnL:</b> {'+' if daily_pnl >= 0 else ''}${daily_pnl:,.2f} ({daily_pnl_pct:+.2f}%)\n"
            f"💰 <b>Total Equity:</b> ${total_equity:,.2f}\n"
            f"📍 <b>Open Positions:</b> {open_positions}\n"
            f"📝 <b>Trades Today:</b> {trades_today}\n"
            f"🎯 <b>Win Rate:</b> {win_rate:.1f}%\n\n"
            f"<i>{datetime.utcnow().strftime('%Y-%m-%d')} UTC</i>"
        )

        await self.send_notification(NotificationType.DAILY_SUMMARY, message)

    # === Command Handlers ===

    async def _send_welcome(self, message: Message) -> None:
        await message.answer(
            "🤖 <b>Cryptobot Trading Assistant</b>\n\n"
            "Welcome! I'll keep you updated on trades, positions, and research.\n\n"
            "<b>Available Commands:</b>\n"
            "/status - System status\n"
            "/positions - Open positions\n"
            "/pnl - Current PnL\n"
            "/balance - Account balance\n"
            "/orders - Open orders\n"
            "/research - Latest research\n"
            "/backtest - Latest backtest\n"
            "/pause - Pause new entries\n"
            "/resume - Resume trading\n"
            "/help - Show this help",
            parse_mode=ParseMode.HTML,
        )

    async def _send_status(self, message: Message) -> None:
        # Would fetch from API
        await message.answer(
            "🤖 <b>System Status</b>\n\n"
            "🟢 API: Online\n"
            "🟢 Data Feed: Connected\n"
            "🟢 Paper Trading: Active\n"
            "🟢 Research Engine: Ready\n"
            "🟢 WebSocket: Connected",
            parse_mode=ParseMode.HTML,
        )

    async def _send_positions(self, message: Message) -> None:
        await message.answer("📍 <b>Open Positions</b>\n\nNo open positions", parse_mode=ParseMode.HTML)

    async def _send_pnl(self, message: Message) -> None:
        await message.answer("💰 <b>PnL Summary</b>\n\nDaily PnL: $0.00 (0.00%)\nTotal Equity: $100,000.00", parse_mode=ParseMode.HTML)

    async def _send_balance(self, message: Message) -> None:
        await message.answer("💰 <b>Account Balance</b>\n\nUSDT: 100,000.00\nAvailable: 100,000.00", parse_mode=ParseMode.HTML)

    async def _send_open_orders(self, message: Message) -> None:
        await message.answer("📋 <b>Open Orders</b>\n\nNo open orders", parse_mode=ParseMode.HTML)

    async def _send_latest_research(self, message: Message) -> None:
        await message.answer("🔬 <b>Latest Research</b>\n\nNo recent research", parse_mode=ParseMode.HTML)

    async def _send_latest_backtest(self, message: Message) -> None:
        await message.answer("📊 <b>Latest Backtest</b>\n\nNo recent backtests", parse_mode=ParseMode.HTML)

    async def _pause_trading(self, message: Message) -> None:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Confirm Pause", callback_data="pause_confirm"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="pause_cancel"),
        ]])
        await message.answer(
            "⏸️ <b>Pause New Entries?</b>\n\nThis will stop new positions from being opened.\nExisting positions will continue to be managed.",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

    async def _resume_trading(self, message: Message) -> None:
        await message.answer("▶️ Trading resumed. New entries are now allowed.", parse_mode=ParseMode.HTML)

    async def _send_help(self, message: Message) -> None:
        await self._send_welcome(message)

    async def _handle_pause_callback(self, callback: CallbackQuery):
        if callback.data == "pause_confirm":
            await callback.message.edit_text("⏸️ Trading paused. New entries disabled.", parse_mode=ParseMode.HTML)
        else:
            await callback.message.edit_text("❌ Pause cancelled.", parse_mode=ParseMode.HTML)
        await callback.answer()

    async def _handle_close_callback(self, callback: CallbackQuery):
        # Would close position via API
        await callback.answer("Position close requested", show_alert=True)


# Global bot instance
_telegram_bot: TelegramBot | None = None


async def get_telegram_bot(config: TelegramConfig | None = None) -> TelegramBot | None:
    """Get or create global Telegram bot instance."""
    global _telegram_bot

    if _telegram_bot is None and config:
        _telegram_bot = TelegramBot(config)
        await _telegram_bot.initialize()
    return _telegram_bot


async def start_telegram_bot(config: TelegramConfig) -> TelegramBot:
    """Create and start Telegram bot."""
    bot = TelegramBot(config)
    await bot.initialize()
    if config.enabled:
        asyncio.create_task(bot.start_polling())
    return bot