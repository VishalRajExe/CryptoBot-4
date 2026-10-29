"""
Tool registry with permission gating.
Adapted from OpenTerminalUI's ToolRegistry and Vibe-Trading's ToolRegistry.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from cryptobot.config.settings import settings

logger = logging.getLogger(__name__)


class WriteClass(str, Enum):
    """Tool write permission level."""

    NONE = "none"       # Read-only, safe for any agent
    SOFT = "soft"       # Can modify local state, not execute trades
    ORDER = "order"     # Can place/modify/cancel orders


@dataclass
class ToolSpec:
    """Tool specification with metadata."""

    name: str
    description: str
    function: Callable
    write_class: WriteClass = WriteClass.NONE
    parameters: dict[str, Any] = field(default_factory=dict)
    returns: str = "Any"
    category: str = "general"
    requires_auth: bool = False
    rate_limit: int | None = None  # calls per minute

    async def __call__(self, *args, **kwargs) -> Any:
        return await self.function(*args, **kwargs)


class ToolRegistry:
    """
    Registry for agent tools with permission gating.

    Features:
    - Write class filtering (none/soft/order)
    - Rate limiting
    - Category organization
    - MCP server exposure
    """

    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}
        self._categories: dict[str, list[str]] = {}
        self._rate_limits: dict[str, asyncio.Semaphore] = {}

    def register(
        self,
        name: str,
        description: str,
        function: Callable,
        write_class: WriteClass = WriteClass.NONE,
        parameters: dict[str, Any] | None = None,
        returns: str = "Any",
        category: str = "general",
        requires_auth: bool = False,
        rate_limit: int | None = None,
    ) -> ToolSpec:
        """Register a new tool."""
        spec = ToolSpec(
            name=name,
            description=description,
            function=function,
            write_class=write_class,
            parameters=parameters or {},
            returns=returns,
            category=category,
            requires_auth=requires_auth,
            rate_limit=rate_limit,
        )

        if rate_limit:
            self._rate_limits[name] = asyncio.Semaphore(rate_limit)

        self._tools[name] = spec
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(name)

        logger.debug(f"Registered tool: {name} ({write_class.value})")
        return spec

    def get(self, name: str) -> ToolSpec | None:
        """Get tool by name."""
        return self._tools.get(name)

    def get_category(self, category: str) -> list[ToolSpec]:
        """Get all tools in a category."""
        return [self._tools[name] for name in self._categories.get(category, [])]

    def list_tools(self, write_class: WriteClass | None = None) -> list[ToolSpec]:
        """List all tools, optionally filtered by write class."""
        tools = list(self._tools.values())
        if write_class:
            tools = [t for t in tools if t.write_class == write_class]
        return tools

    def filtered(self, allow_writes: WriteClass = WriteClass.NONE) -> "ToolRegistry":
        """
        Create a filtered view of the registry.

        Args:
            allow_writes: Maximum write class to allow

        Returns:
            New ToolRegistry with only permitted tools
        """
        filtered_registry = ToolRegistry()
        max_level = {"none": 0, "soft": 1, "order": 2}[allow_writes.value]

        for name, spec in self._tools.items():
            spec_level = {"none": 0, "soft": 1, "order": 2}[spec.write_class.value]
            if spec_level <= max_level:
                filtered_registry._tools[name] = spec
                if spec.category not in filtered_registry._categories:
                    filtered_registry._categories[spec.category] = []
                filtered_registry._categories[spec.category].append(name)

        return filtered_registry

    async def call(self, name: str, *args, **kwargs) -> Any:
        """Call a tool with rate limiting."""
        spec = self._tools.get(name)
        if not spec:
            raise ValueError(f"Tool not found: {name}")

        # Rate limiting
        if name in self._rate_limits:
            async with self._rate_limits[name]:
                return await spec(*args, **kwargs)

        return await spec(*args, **kwargs)

    def get_mcp_tools(self) -> list[dict[str, Any]]:
        """Get tools formatted for MCP server."""
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
                "returns": spec.returns,
                "write_class": spec.write_class.value,
                "category": spec.category,
            }
            for spec in self._tools.values()
            if spec.write_class != WriteClass.ORDER  # Don't expose order tools via MCP
        ]


# Global tool registry
tool_registry = ToolRegistry()


# Convenience decorator
def tool(
    name: str | None = None,
    description: str = "",
    write_class: WriteClass = WriteClass.NONE,
    category: str = "general",
    **kwargs,
) -> Callable:
    """Decorator to register a tool."""

    def decorator(fn: Callable) -> Callable:
        tool_name = name or fn.__name__
        tool_registry.register(
            name=tool_name,
            description=description or fn.__doc__ or "",
            function=fn,
            write_class=write_class,
            category=category,
            **kwargs,
        )
        return fn

    return decorator