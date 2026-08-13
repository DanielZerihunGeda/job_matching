"""Async Neo4j connector shared by FastAPI endpoints and application services."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from contextlib import suppress
from typing import Any, Literal, LiteralString, cast

from neo4j import (
    AsyncDriver,
    AsyncGraphDatabase,
    AsyncSession,
    EagerResult,
    Query,
    READ_ACCESS,
    RoutingControl,
    WRITE_ACCESS,
)

from job_matching.core.config import Neo4jSettings

DriverFactory = Callable[..., AsyncDriver]
AccessMode = Literal["READ", "WRITE"]


class Neo4jConnector:
    """Own a process-local async driver and its connection pool.

    The connector is intentionally application-scoped. Constructing a driver per
    request would repeatedly rebuild the pool and add avoidable connection latency.
    """

    def __init__(
        self,
        settings: Neo4jSettings,
        *,
        environment: Literal["development", "testing", "staging", "production"],
        driver_factory: DriverFactory = AsyncGraphDatabase.driver,
        user_agent: str = "job-matching-api",
    ) -> None:
        self.settings = settings
        self._environment = environment
        self._driver_factory = driver_factory
        self._user_agent = user_agent
        self._driver: AsyncDriver | None = None
        self._lifecycle_lock = asyncio.Lock()

    @property
    def is_started(self) -> bool:
        """Return whether this connector currently owns a live driver."""

        return self._driver is not None

    @property
    def driver(self) -> AsyncDriver:
        """Expose the shared driver for advanced driver APIs when necessary."""

        if self._driver is None:
            raise RuntimeError("Neo4j connector has not been started")
        return self._driver

    async def start(self) -> None:
        """Create the driver and fail startup if Neo4j is not reachable."""

        async with self._lifecycle_lock:
            if self._driver is not None:
                return

            self.settings.validate_for_environment(self._environment)
            candidate = self._driver_factory(
                self.settings.uri,
                auth=(
                    self.settings.username,
                    self.settings.password.get_secret_value(),
                ),
                max_connection_pool_size=self.settings.max_connection_pool_size,
                connection_acquisition_timeout=(
                    self.settings.connection_acquisition_timeout_seconds
                ),
                connection_timeout=self.settings.connection_timeout_seconds,
                max_connection_lifetime=(
                    self.settings.max_connection_lifetime_seconds
                ),
                liveness_check_timeout=(
                    self.settings.liveness_check_timeout_seconds
                ),
                max_transaction_retry_time=(
                    self.settings.max_transaction_retry_time_seconds
                ),
                keep_alive=self.settings.keep_alive,
                user_agent=self._user_agent,
            )
            try:
                async with asyncio.timeout(self.settings.startup_timeout_seconds):
                    await candidate.verify_connectivity()
            except BaseException:
                with suppress(Exception):
                    await candidate.close()
                raise

            self._driver = candidate

    async def close(self) -> None:
        """Close the pool; repeated shutdown calls are safe."""

        async with self._lifecycle_lock:
            driver, self._driver = self._driver, None
            if driver is not None:
                await driver.close()

    async def verify_connectivity(self) -> None:
        """Check connectivity using the existing driver and pool."""

        async with asyncio.timeout(self.settings.connection_timeout_seconds):
            await self.driver.verify_connectivity()

    def session(self, *, access_mode: AccessMode = "WRITE") -> AsyncSession:
        """Create a session for streaming or multi-query managed transactions.

        Callers must use the returned value as an ``async with`` context manager.
        The fixed database avoids the driver's home-database discovery round trip.
        """

        if access_mode not in {"READ", "WRITE"}:
            raise ValueError("access_mode must be READ or WRITE")
        default_access_mode = READ_ACCESS if access_mode == "READ" else WRITE_ACCESS
        return self.driver.session(
            database=self.settings.database,
            default_access_mode=default_access_mode,
            fetch_size=self.settings.fetch_size,
        )

    async def execute_read(
        self,
        query: LiteralString | Query,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> EagerResult:
        """Execute and retry an eager query routed to a read server."""

        return await self._execute(
            query,
            parameters,
            routing=RoutingControl.READ,
            timeout_seconds=timeout_seconds,
        )

    async def execute_write(
        self,
        query: LiteralString | Query,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout_seconds: float | None = None,
    ) -> EagerResult:
        """Execute and retry an eager query routed to a write server."""

        return await self._execute(
            query,
            parameters,
            routing=RoutingControl.WRITE,
            timeout_seconds=timeout_seconds,
        )

    async def _execute(
        self,
        query: LiteralString | Query,
        parameters: Mapping[str, Any] | None,
        *,
        routing: RoutingControl,
        timeout_seconds: float | None,
    ) -> EagerResult:
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        configured_query = query
        if isinstance(query, str):
            configured_query = Query(
                query,
                timeout=timeout_seconds or self.settings.query_timeout_seconds,
                metadata={"application": self._user_agent},
            )
        elif timeout_seconds is not None:
            raise ValueError("timeout_seconds cannot override a neo4j.Query")

        result = await self.driver.execute_query(
            configured_query,
            parameters_=dict(parameters or {}),
            routing_=routing,
            database_=self.settings.database,
        )
        return cast(EagerResult, result)


__all__ = ["AccessMode", "Neo4jConnector"]
