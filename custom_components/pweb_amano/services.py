"""Services for PWEB Amano — discount registration (할인등록)."""
from __future__ import annotations

import logging
import string
from datetime import date, timedelta

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util

from .api import PwebAmanoApiClient
from .const import DOMAIN, SERVICE_LIST_UNREGISTERED_VEHICLES, SERVICE_REGISTER_DISCOUNT
from .exceptions import PwebAmanoError

_LOGGER = logging.getLogger(__name__)

ATTR_DEVICE_ID = "device_id"
ATTR_CAR_NO = "car_no"
ATTR_DISCOUNT_TYPE = "discount_type"
ATTR_MEMO = "memo"
ATTR_ENTRY_DATE = "entry_date"
ATTR_DAYS = "days"

SERVICE_REGISTER_DISCOUNT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_CAR_NO): cv.string,
        vol.Required(ATTR_DISCOUNT_TYPE): cv.string,
        vol.Optional(ATTR_MEMO, default=""): cv.string,
        vol.Optional(ATTR_ENTRY_DATE): cv.date,
    }
)
SERVICE_LIST_UNREGISTERED_VEHICLES_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_DAYS, default=2): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=7)
        ),
    }
)


def _async_resolve_client(hass: HomeAssistant, device_id: str | None) -> PwebAmanoApiClient:
    """Resolve a service call's device_id to that config entry's API client.

    device_id is optional: with only one PWEB Amano site configured, that's
    the only thing it could mean, so use it automatically rather than
    forcing a pointless pick every call.
    """
    if device_id is None:
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("no PWEB Amano site is configured")
        if len(entries) > 1:
            sites = ", ".join(entry.title for entry in entries)
            raise HomeAssistantError(
                f"more than one PWEB Amano site is configured ({sites}) - "
                "specify device_id"
            )
        return entries[0].runtime_data.client

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device is None:
        raise HomeAssistantError(f"unknown device: {device_id}")

    entry = hass.config_entries.async_get_entry(device.config_entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise HomeAssistantError(f"device {device_id} is not a PWEB Amano device")

    return entry.runtime_data.client


def async_register_services(hass: HomeAssistant) -> None:
    """Register the domain's services once, regardless of entry count."""
    if not hass.services.has_service(DOMAIN, SERVICE_REGISTER_DISCOUNT):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REGISTER_DISCOUNT,
            _async_register_discount(hass),
            schema=SERVICE_REGISTER_DISCOUNT_SCHEMA,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_LIST_UNREGISTERED_VEHICLES):
        hass.services.async_register(
            DOMAIN,
            SERVICE_LIST_UNREGISTERED_VEHICLES,
            _async_list_unregistered_vehicles(hass),
            schema=SERVICE_LIST_UNREGISTERED_VEHICLES_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )


async def async_register_discount_for_car(
    client: PwebAmanoApiClient,
    car_no: str,
    discount_type: str,
    memo: str = "",
    entry_date: date | None = None,
) -> str:
    """Find a currently-parked car and register a discount for it.

    Shared by the register_discount service and the LLM tool. Returns the
    plate the discount was registered to.
    """
    # Visitor cars are the common case, and the caller usually doesn't
    # know (or care) whether the portal logged the entry as yesterday or
    # today (e.g. an overnight visitor) - the portal has no ranged
    # search, so search both days, unless the caller pinned an explicit
    # entry_date.
    if entry_date:
        candidate_dates = [entry_date]
    else:
        today = dt_util.now().date()
        candidate_dates = [today - timedelta(days=1), today]

    try:
        # Unlike the coordinator's poll, this can run any time (e.g. from an
        # LLM conversation) - don't rely on the last poll's session.
        await client.async_login()
        rows: dict[int, dict] = {}
        for candidate_date in candidate_dates:
            for row in await client.async_find_parked_entry(
                car_no, candidate_date.strftime("%Y%m%d")
            ):
                rows[row["id"]] = row
        row = _match_parked_entry(car_no, list(rows.values()))
        await client.async_register_discount(
            pe_id=row["id"],
            car_no=row["carNo"],
            discount_type=discount_type,
            memo=memo,
        )
    except PwebAmanoError as err:
        raise HomeAssistantError(str(err)) from err
    return row["carNo"]


def _match_parked_entry(car_no: str, rows: list[dict]) -> dict:
    """Pick the one parked entry that is really `car_no`.

    The portal's search only matches one of the plate's digit groups (see
    api.async_find_parked_entry), so it can return other cars sharing those
    digits - e.g. both 12가3456 and 77나3456 for "12가3456". Registering
    the first row blindly would spend the discount on the wrong car, so
    require an exact plate match. A digits-only car_no ("3456") is accepted
    only when exactly one parked plate ends with it.
    """
    wanted = "".join(car_no.split())
    plates = {row["id"]: "".join(str(row.get("carNo") or "").split()) for row in rows}
    matches = [row for row in rows if plates[row["id"]] == wanted]
    if not matches and wanted.isdigit():
        matches = [row for row in rows if plates[row["id"]].endswith(wanted)]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise HomeAssistantError(f"차량 '{car_no}'을(를) 주차장에서 찾을 수 없습니다")
    found = ", ".join(sorted(plates[row["id"]] for row in matches))
    raise HomeAssistantError(
        f"'{car_no}'에 해당하는 주차 차량이 여러 대입니다 ({found}) - "
        "전체 번호판을 지정하세요"
    )


async def async_find_unregistered_vehicles(
    client: PwebAmanoApiClient, days: int
) -> list[dict]:
    """List parked cars from the last `days` days with no discount yet.

    Shared by the list_unregistered_vehicles service and the LLM tool.
    """
    today = dt_util.now().date()
    entry_dates = [
        (today - timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(days)
    ]

    try:
        # There's no "list every parked car" endpoint (see AGENTS.md) -
        # the search only works by car number, so cast the widest
        # possible net: every plate has at least one of these ten
        # digits somewhere, so searching all of them finds every car.
        await client.async_login()
        found: dict[int, dict] = {}
        for entry_date in entry_dates:
            for digit in string.digits:
                for row in await client.async_find_parked_entry(digit, entry_date):
                    found[row["id"]] = row
    except PwebAmanoError as err:
        raise HomeAssistantError(str(err)) from err

    return [
        {
            "car_no": row.get("carNo"),
            "entry_date": row.get("entryDateToString"),
            "minutes_parked": row.get("incar_min"),
        }
        for row in found.values()
        if str(row.get("dscnt_cnt")) == "0"
    ]


def _async_register_discount(hass: HomeAssistant):
    async def _service(call: ServiceCall) -> None:
        await async_register_discount_for_car(
            _async_resolve_client(hass, call.data.get(ATTR_DEVICE_ID)),
            car_no=call.data[ATTR_CAR_NO],
            discount_type=call.data[ATTR_DISCOUNT_TYPE],
            memo=call.data.get(ATTR_MEMO, ""),
            entry_date=call.data.get(ATTR_ENTRY_DATE),
        )

    return _service


def _async_list_unregistered_vehicles(hass: HomeAssistant):
    async def _service(call: ServiceCall) -> ServiceResponse:
        client = _async_resolve_client(hass, call.data.get(ATTR_DEVICE_ID))
        vehicles = await async_find_unregistered_vehicles(client, call.data[ATTR_DAYS])
        return {"vehicles": vehicles}

    return _service
