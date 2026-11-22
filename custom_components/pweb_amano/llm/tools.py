"""LLM tools for PWEB Amano parking management."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.util import dt as dt_util

from ..const import CONF_CAR_PLATES, DOMAIN
from ..coordinator import PwebAmanoCoordinator
from ..services import async_find_unregistered_vehicles, async_register_discount_for_car

MAX_HISTORY_DAYS = 92


def _format_portal_datetime(value: str | None) -> str | None:
    """yyyyMMddHHmmss (portal wall-clock time) -> 'YYYY-MM-DD HH:MM'.

    Anything that isn't a bare digit run is passed through unchanged.
    """
    value = (value or "").strip()
    if not value.isdigit():
        return value or None
    if len(value) >= 12:
        return datetime.strptime(value[:12], "%Y%m%d%H%M").strftime("%Y-%m-%d %H:%M")
    if len(value) >= 8:
        return datetime.strptime(value[:8], "%Y%m%d").strftime("%Y-%m-%d")
    return value or None


class BasePwebAmanoTool(llm.Tool):
    """Resolves the bound config entry's coordinator on demand."""

    integration = DOMAIN

    def __init__(self, entry_id: str) -> None:
        super().__init__()
        self.entry_id = entry_id

    def entry(self, hass: HomeAssistant) -> ConfigEntry | None:
        return hass.config_entries.async_get_entry(self.entry_id)

    def coordinator(self, hass: HomeAssistant) -> PwebAmanoCoordinator | None:
        entry = self.entry(hass)
        return getattr(entry, "runtime_data", None) if entry is not None else None

    @staticmethod
    def error(message: str) -> llm.ToolResult:
        return llm.ToolResult(data={"error": message}, error=True)


class GetParkingStatusTool(BasePwebAmanoTool):
    name = "pweb_amano__get_parking_status"
    title = "Get parking status"
    annotations = llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    description = (
        "Return the parking account's current status: remaining discount "
        "balance (KRW), today's discount registration counts, the user's own "
        "tracked car plates, and the site's discount types (id + name). Call "
        "this for questions about the balance or today's usage, and before "
        "pweb_amano__register_discount to look up a discount type id."
    )
    parameters = vol.Schema({})

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> llm.ToolResult:
        entry = self.entry(hass)
        coordinator = self.coordinator(hass)
        if entry is None or coordinator is None or coordinator.data is None:
            return self.error("Parking data is not ready.")
        data = coordinator.data
        summary = data.get("registration_summary") or {}
        last_sync = data.get("last_sync")
        return llm.ToolResult(
            data={
                "remaining_discount_balance_krw": data.get("balance"),
                "today_registrations": {
                    "total": summary.get("used_cnt"),
                    "free": summary.get("used_basic"),
                    "paid": summary.get("used_charge"),
                    "discount_amount_krw": summary.get("discount_price"),
                },
                "tracked_car_plates": [
                    p for p in (entry.options.get(CONF_CAR_PLATES) or []) if p
                ],
                "discount_types": [
                    {"id": str(type_id), "name": label}
                    for type_id, label in (data.get("discount_types") or {}).items()
                ],
                "last_sync": dt_util.as_local(last_sync).isoformat()
                if last_sync
                else None,
            }
        )


class ListUnregisteredVehiclesTool(BasePwebAmanoTool):
    name = "pweb_amano__list_unregistered_vehicles"
    title = "List unregistered parked vehicles"
    annotations = llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=True
    )
    description = (
        "List cars currently parked in the lot that entered yesterday or "
        "today and have no parking discount registered yet. Call this when "
        "the user asks which cars (e.g. a visitor) still need a discount, or "
        "to find a car's exact plate before registering. Slow: it queries the "
        "portal many times."
    )
    parameters = vol.Schema({})

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> llm.ToolResult:
        coordinator = self.coordinator(hass)
        if coordinator is None:
            return self.error("PWEB Amano site is not loaded.")
        try:
            # Same yesterday+today window register_discount searches - an
            # older car couldn't be registered through these tools anyway.
            vehicles = await async_find_unregistered_vehicles(coordinator.client, 2)
        except HomeAssistantError as err:
            return self.error(str(err))
        return llm.ToolResult(data={"count": len(vehicles), "vehicles": vehicles})


class RegisterDiscountTool(BasePwebAmanoTool):
    name = "pweb_amano__register_discount"
    title = "Register parking discount"
    annotations = llm.ToolAnnotations(
        read_only=False, destructive=False, idempotent=False, open_world=True
    )
    description = (
        "Register a parking discount for a car that is currently parked "
        "(the user's own, a family member's, or a visitor's). This consumes "
        "the account's discount quota/balance and cannot be undone here, so "
        "confirm the plate and discount type with the user unless they "
        "stated both explicitly. `discount_type` must be an id from "
        "pweb_amano__get_parking_status. `car_no` is the plate; its digit "
        "part alone (e.g. '3456') also matches."
    )
    parameters = vol.Schema(
        {
            vol.Required("car_no"): str,
            vol.Required("discount_type"): str,
            vol.Optional("memo"): str,
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> llm.ToolResult:
        coordinator = self.coordinator(hass)
        if coordinator is None or coordinator.data is None:
            return self.error("Parking data is not ready.")
        args = tool_input.tool_args
        discount_type = str(args["discount_type"])
        discount_types = {
            str(type_id): label
            for type_id, label in (coordinator.data.get("discount_types") or {}).items()
        }
        if discount_types and discount_type not in discount_types:
            return self.error(
                f"Unknown discount_type '{discount_type}'. Valid ids: "
                f"{', '.join(sorted(discount_types))}"
            )
        try:
            await async_register_discount_for_car(
                coordinator.client,
                car_no=args["car_no"],
                discount_type=discount_type,
                memo=args.get("memo") or "",
            )
        except HomeAssistantError as err:
            return self.error(str(err))
        # Let a follow-up status call see the updated balance.
        await coordinator.async_request_refresh()
        return llm.ToolResult(
            data={
                "success": True,
                "car_no": args["car_no"],
                "discount_type": discount_types.get(discount_type, discount_type),
            }
        )


class GetParkingHistoryTool(BasePwebAmanoTool):
    name = "pweb_amano__get_parking_history"
    title = "Get parking history"
    annotations = llm.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=True
    )
    description = (
        "Return discount registrations made by this account between "
        "start_date and end_date (YYYY-MM-DD, inclusive, at most "
        f"{MAX_HISTORY_DAYS} days), each with the car's entry (입차) and exit "
        "(출차) time. Optional car_no filters to plates containing it. Call "
        "this for questions like when a car came in or left, or how often a "
        "visitor parked. Only cars that got a discount appear."
    )
    parameters = vol.Schema(
        {
            vol.Required("start_date"): str,
            vol.Required("end_date"): str,
            vol.Optional("car_no"): str,
        }
    )

    async def async_call(
        self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> llm.ToolResult:
        coordinator = self.coordinator(hass)
        if coordinator is None:
            return self.error("PWEB Amano site is not loaded.")
        args = tool_input.tool_args
        start = dt_util.parse_date(args["start_date"])
        end = dt_util.parse_date(args["end_date"])
        if start is None or end is None:
            return self.error("start_date and end_date must be YYYY-MM-DD.")
        if end < start:
            return self.error("end_date is before start_date.")
        if end - start > timedelta(days=MAX_HISTORY_DAYS - 1):
            return self.error(f"Date range must be at most {MAX_HISTORY_DAYS} days.")

        try:
            rows = await coordinator.async_get_discount_events(
                start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
            )
        except HomeAssistantError as err:
            return self.error(str(err))

        car_no = (args.get("car_no") or "").replace(" ", "")
        records: list[dict[str, Any]] = [
            {
                "car_no": row.get("carno"),
                "discount": row.get("discount_name"),
                "entry_time": _format_portal_datetime(row.get("entry_date")),
                "exit_time": _format_portal_datetime(row.get("dtOutDate")),
                "registered_at": _format_portal_datetime(row.get("reg_date")),
                "memo": row.get("memo") or None,
            }
            for row in rows
            if not car_no or car_no in (row.get("carno") or "")
        ]
        return llm.ToolResult(data={"count": len(records), "records": records})


TOOLS: list[type[BasePwebAmanoTool]] = [
    GetParkingStatusTool,
    ListUnregisteredVehiclesTool,
    RegisterDiscountTool,
    GetParkingHistoryTool,
]
