"""
glpi_utils._resource
~~~~~~~~~~~~~~~~~~~~

ItemProxy and AsyncItemProxy – thin accessor objects that bind an item-type
name to a session so callers can write ``api.ticket.get(1)`` instead of
calling lower-level methods directly.

These are created dynamically by GlpiAPI / AsyncGlpiAPI via ``__getattr__``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api import GlpiAPI
    from .aio import AsyncGlpiAPI


class ItemProxy:
    """Synchronous resource accessor for a single GLPI item-type.

    Parameters
    ----------
    session : GlpiAPI
        Authenticated session to delegate HTTP calls to.
    itemtype : str
        GLPI item-type name, e.g. ``"Ticket"``, ``"Computer"``.
    """

    def __init__(self, session: "GlpiAPI", itemtype: str) -> None:
        self._session = session
        self._itemtype = itemtype

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

    def get(self, item_id: int, **kwargs: Any) -> dict:
        """Return a single item by *item_id*.

        Parameters
        ----------
        item_id : int
            Numeric ID of the resource.
        **kwargs
            Any extra query-string parameters supported by the GLPI REST API
            for this endpoint (e.g. ``expand_dropdowns=True``,
            ``with_networkports=True``).
        """
        return self._session.get_item(self._itemtype, item_id, **kwargs)

    def get_all(self, **kwargs: Any) -> list[dict]:
        """Return all items of this type (auto-paginated).

        Parameters
        ----------
        **kwargs
            Query parameters: ``range``, ``sort``, ``order``,
            ``searchText``, ``is_deleted``, ``add_keys_names``, …
        """
        return self._session.get_all_items(self._itemtype, **kwargs)

    def search(self, **kwargs: Any) -> dict:
        """Run the GLPI search engine against this item-type.

        Parameters
        ----------
        **kwargs
            Search criteria, ``criteria``, ``sort``, ``order``,
            ``range``, ``forcedisplay``, …
        """
        return self._session.search(self._itemtype, **kwargs)

    def create(self, input_data: dict | list[dict], **kwargs: Any) -> dict | list:
        """Create one or several items.

        Parameters
        ----------
        input_data : dict | list[dict]
            Field values for the new item(s).
        """
        return self._session.create_item(self._itemtype, input_data, **kwargs)

    def update(self, input_data: dict | list[dict], **kwargs: Any) -> list:
        """Update one or several items.

        Each dict in *input_data* must contain an ``"id"`` key.
        """
        return self._session.update_item(self._itemtype, input_data, **kwargs)

    def delete(
        self,
        input_data: dict | list[dict],
        force_purge: bool = False,
        history: bool = True,
    ) -> list:
        """Delete one or several items.

        Parameters
        ----------
        input_data : dict | list[dict]
            Each dict must contain an ``"id"`` key.
        force_purge : bool
            Bypass trash and permanently delete.
        history : bool
            Log the deletion in history.
        """
        return self._session.delete_item(
            self._itemtype,
            input_data,
            force_purge=force_purge,
            history=history,
        )

    def get_sub_items(
        self, item_id: int, sub_itemtype: str, **kwargs: Any
    ) -> list[dict]:
        """Return sub-items of *sub_itemtype* for the given parent *item_id*."""
        return self._session.get_sub_items(
            self._itemtype, item_id, sub_itemtype, **kwargs
        )

    def add_sub_item(
        self, item_id: int, sub_itemtype: str, input_data: dict, **kwargs: Any
    ) -> dict:
        """Add a sub-item (e.g. a followup or a task to a ticket)."""
        return self._session.add_sub_item(
            self._itemtype, item_id, sub_itemtype, input_data, **kwargs
        )

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"ItemProxy(itemtype={self._itemtype!r})"


class AsyncItemProxy:
    """Asynchronous resource accessor for a single GLPI item-type."""

    def __init__(self, session: "AsyncGlpiAPI", itemtype: str) -> None:
        self._session = session
        self._itemtype = itemtype

    async def get(self, item_id: int, **kwargs: Any) -> dict:
        return await self._session.get_item(self._itemtype, item_id, **kwargs)

    async def get_all(self, **kwargs: Any) -> list[dict]:
        return await self._session.get_all_items(self._itemtype, **kwargs)

    async def search(self, **kwargs: Any) -> dict:
        return await self._session.search(self._itemtype, **kwargs)

    async def create(self, input_data: dict | list[dict], **kwargs: Any) -> dict | list:
        return await self._session.create_item(self._itemtype, input_data, **kwargs)

    async def update(self, input_data: dict | list[dict], **kwargs: Any) -> list:
        return await self._session.update_item(self._itemtype, input_data, **kwargs)

    async def delete(
        self,
        input_data: dict | list[dict],
        force_purge: bool = False,
        history: bool = True,
    ) -> list:
        return await self._session.delete_item(
            self._itemtype,
            input_data,
            force_purge=force_purge,
            history=history,
        )

    async def get_sub_items(
        self, item_id: int, sub_itemtype: str, **kwargs: Any
    ) -> list[dict]:
        return await self._session.get_sub_items(
            self._itemtype, item_id, sub_itemtype, **kwargs
        )

    async def add_sub_item(
        self, item_id: int, sub_itemtype: str, input_data: dict, **kwargs: Any
    ) -> dict:
        return await self._session.add_sub_item(
            self._itemtype, item_id, sub_itemtype, input_data, **kwargs
        )

    def __repr__(self) -> str:
        return f"AsyncItemProxy(itemtype={self._itemtype!r})"
