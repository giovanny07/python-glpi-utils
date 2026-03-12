"""
glpi_utils._resource
~~~~~~~~~~~~~~~~~~~~

ItemProxy and AsyncItemProxy – thin accessor objects that bind an item-type
name to a session so callers can write ``api.ticket.get(1)`` instead of
calling lower-level methods directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Iterator

if TYPE_CHECKING:
    from .api import GlpiAPI
    from .aio import AsyncGlpiAPI


class ItemProxy:
    """Synchronous resource accessor for a single GLPI item-type."""

    def __init__(self, session: "GlpiAPI", itemtype: str) -> None:
        self._session = session
        self._itemtype = itemtype

    def get(self, item_id: int, **kwargs: Any) -> dict:
        """Return a single item by *item_id*."""
        return self._session.get_item(self._itemtype, item_id, **kwargs)

    def get_all(self, **kwargs: Any) -> list:
        """Return a single page of items (default range ``0-49``).

        Use :meth:`get_all_pages` to fetch every item automatically.
        """
        return self._session.get_all_items(self._itemtype, **kwargs)

    def get_all_pages(self, page_size: int = 50, **kwargs: Any) -> list:
        """Fetch **all** items across all pages automatically.

        Examples
        --------
        ::

            all_tickets = api.ticket.get_all_pages()
            open_tickets = api.ticket.get_all_pages(searchText={"status": "1"})
        """
        return self._session.get_all_pages(self._itemtype, page_size=page_size, **kwargs)

    def iter_pages(self, page_size: int = 50, **kwargs: Any) -> Iterator[list]:
        """Yield one page at a time — memory-efficient for large datasets.

        Examples
        --------
        ::

            for page in api.ticket.iter_pages(page_size=100):
                for ticket in page:
                    process(ticket)
        """
        return self._session.iter_pages(self._itemtype, page_size=page_size, **kwargs)

    def search(self, **kwargs: Any) -> dict:
        """Run the GLPI search engine against this item-type."""
        return self._session.search(self._itemtype, **kwargs)

    def create(self, input_data: Any, **kwargs: Any) -> Any:
        """Create one or several items."""
        return self._session.create_item(self._itemtype, input_data, **kwargs)

    def update(self, input_data: Any, **kwargs: Any) -> list:
        """Update one or several items. Each dict must contain an ``"id"`` key."""
        return self._session.update_item(self._itemtype, input_data, **kwargs)

    def delete(
        self,
        input_data: Any,
        force_purge: bool = False,
        history: bool = True,
    ) -> list:
        """Delete one or several items."""
        return self._session.delete_item(
            self._itemtype, input_data,
            force_purge=force_purge, history=history,
        )

    def get_sub_items(self, item_id: int, sub_itemtype: str, **kwargs: Any) -> list:
        """Return sub-items of *sub_itemtype* for the given parent *item_id*."""
        return self._session.get_sub_items(
            self._itemtype, item_id, sub_itemtype, **kwargs
        )

    def add_sub_item(
        self, item_id: int, sub_itemtype: str, input_data: dict, **kwargs: Any
    ) -> dict:
        """Add a sub-item (e.g. a followup or task) to a parent item."""
        return self._session.add_sub_item(
            self._itemtype, item_id, sub_itemtype, input_data, **kwargs
        )

    def __repr__(self) -> str:
        return f"ItemProxy(itemtype={self._itemtype!r})"


class AsyncItemProxy:
    """Asynchronous resource accessor for a single GLPI item-type."""

    def __init__(self, session: "AsyncGlpiAPI", itemtype: str) -> None:
        self._session = session
        self._itemtype = itemtype

    async def get(self, item_id: int, **kwargs: Any) -> dict:
        return await self._session.get_item(self._itemtype, item_id, **kwargs)

    async def get_all(self, **kwargs: Any) -> list:
        """Return a single page of items (default range ``0-49``)."""
        return await self._session.get_all_items(self._itemtype, **kwargs)

    async def get_all_pages(self, page_size: int = 50, **kwargs: Any) -> list:
        """Fetch **all** items across all pages automatically."""
        return await self._session.get_all_pages(self._itemtype, page_size=page_size, **kwargs)

    async def iter_pages(self, page_size: int = 50, **kwargs: Any) -> AsyncIterator[list]:
        """Yield one page at a time asynchronously."""
        async for page in self._session.iter_pages(self._itemtype, page_size=page_size, **kwargs):
            yield page

    async def search(self, **kwargs: Any) -> dict:
        return await self._session.search(self._itemtype, **kwargs)

    async def create(self, input_data: Any, **kwargs: Any) -> Any:
        return await self._session.create_item(self._itemtype, input_data, **kwargs)

    async def update(self, input_data: Any, **kwargs: Any) -> list:
        return await self._session.update_item(self._itemtype, input_data, **kwargs)

    async def delete(
        self,
        input_data: Any,
        force_purge: bool = False,
        history: bool = True,
    ) -> list:
        return await self._session.delete_item(
            self._itemtype, input_data,
            force_purge=force_purge, history=history,
        )

    async def get_sub_items(
        self, item_id: int, sub_itemtype: str, **kwargs: Any
    ) -> list:
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
