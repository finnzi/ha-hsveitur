"""Client for the HS Veitur UsageData API. No Home Assistant imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

from .const import API_TIMEOUT_SECONDS, API_URL, PAGE_SIZE

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
ROW_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
AUTOMATIC_SOURCE = "Sjálfvirkar mælingar"


class HsVeiturError(Exception):
    """Base error."""


class AuthError(HsVeiturError):
    """Credentials rejected (the API answers HTTP 400 almost instantly)."""


class ApiError(HsVeiturError):
    """Any other API failure, including timeouts."""


@dataclass(frozen=True)
class Reading:
    """One usage row."""

    time: datetime  # naive; Iceland is UTC all year, so treated as UTC
    meter_id: str
    delivery_point_id: str
    delivery_point_name: str
    delta_value: float
    index_value: float
    data_source: str

    @property
    def is_automatic(self) -> bool:
        return self.data_source == AUTOMATIC_SOURCE


def parse_response(payload: dict[str, Any]) -> tuple[int, int, list[Reading]]:
    """Return (total_rows, rows_on_page, readings). Accepts the real and the documented shape."""
    values = payload.get("values") if isinstance(payload.get("values"), dict) else payload
    info = values.get("Info") or {}
    rows = values.get("UsageData") or []
    readings = []
    for row in rows:
        if row.get("type_data") != "Rafmagn" or row.get("type") != "A+":
            continue
        if row.get("index_value") is None:
            continue
        readings.append(
            Reading(
                time=datetime.strptime(row["date"], ROW_DATE_FORMAT),
                meter_id=str(row["meter_id"]),
                delivery_point_id=str(row.get("delivery_point_id", "")),
                delivery_point_name=str(row.get("delivery_point_name", "")).strip(", "),
                delta_value=float(row.get("delta_value") or 0),
                index_value=float(row["index_value"]),
                data_source=str(row.get("data_source", "")),
            )
        )
    return int(info.get("TotalNoRows") or len(rows)), len(rows), readings


class HsVeiturClient:
    """Async client. Tokens travel in the query string, so never log URLs."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        public_key: str,
        private_key: str,
        customer_id: str,
    ) -> None:
        self._session = session
        self._params = {
            "public_token": public_key,
            "private_token": private_key,
            "customer_id": customer_id,
        }

    async def _fetch_page(
        self, start: datetime, end: datetime, page: int, page_size: int
    ) -> dict[str, Any]:
        params = {
            **self._params,
            "datefrom": start.strftime(DATE_FORMAT),
            "dateto": end.strftime(DATE_FORMAT),
            "page_size": str(page_size),
            "page": str(page),
        }
        try:
            async with self._session.post(
                API_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS),
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise AuthError("HS Veitur rejected the credentials")
                if resp.status != 200:
                    raise ApiError(f"HS Veitur returned HTTP {resp.status}")
                return await resp.json(content_type=None)
        except TimeoutError as err:
            raise ApiError("Timed out waiting for HS Veitur") from err
        except aiohttp.ClientError as err:
            # str(err) can contain the request URL (with tokens): use only the type.
            raise ApiError(f"Connection error ({type(err).__name__})") from err

    async def validate(self, start: datetime, end: datetime) -> None:
        """One single-row call: raises AuthError/ApiError, otherwise returns."""
        parse_response(await self._fetch_page(start, end, 1, 1))

    async def get_readings(
        self, start: datetime, end: datetime, page_size: int = PAGE_SIZE
    ) -> list[Reading]:
        """Fetch every reading in [start, end], following pages."""
        readings: list[Reading] = []
        page = 1
        while True:
            total, on_page, batch = parse_response(
                await self._fetch_page(start, end, page, page_size)
            )
            readings.extend(batch)
            if not on_page or page * page_size >= total:
                return readings
            page += 1
