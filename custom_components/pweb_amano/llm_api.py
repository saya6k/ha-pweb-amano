"""Opt-in LLM API registration for PWEB Amano.

One ``llm.API`` is registered per config entry (site), so each appears as
its own user-selectable tool source in a conversation agent's LLM API
settings - these tools are never contributed to the shared Assist API.

Keep this module thin: never import the ``llm/`` platform package at module
level, or the tool modules would load on every setup instead of lazily on
the first LLM request (see ``llm/__init__.py``).
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .const import DOMAIN, LLM_API_NAME


class PwebAmanoAPI(llm.API):
    """An ``llm.API`` bound to a single PWEB Amano config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass=hass,
            id=f"{DOMAIN}__{entry.entry_id}",
            name=f"{LLM_API_NAME} — {entry.title}",
        )

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return the instance of the API."""
        from homeassistant.components.llm import (  # noqa: PLC0415
            async_get_tools as async_get_platform_tools,
        )

        llm_tools = await async_get_platform_tools(self.hass, llm_context, self.id)
        return llm.APIInstance(
            api=self,
            api_prompt=llm_tools.prompt or "",
            llm_context=llm_context,
            tools=llm_tools.tools,
        )


def async_register_llm_api(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register this entry's LLM API; auto-unregisters on unload."""
    entry.async_on_unload(llm.async_register_api(hass, PwebAmanoAPI(hass, entry)))
