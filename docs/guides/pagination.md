# Auto-pagination

GLPI paginates results via a `range` query parameter (`0-49`, `50-99`, …) and
reports the grand total in the `Content-Range` response header (`0-49/1337`).

`python-glpi-utils` handles all of that transparently.

---

## get_all_pages

Fetches every item and returns a single flat list:

```python
# All tickets
tickets = api.ticket.get_all_pages()

# With filters
open_tickets = api.ticket.get_all_pages(
    sort="date_mod",
    order="DESC",
    is_deleted=False,
)

# Larger pages = fewer round-trips
computers = api.computer.get_all_pages(page_size=100, expand_dropdowns=True)

print(f"{len(tickets)} tickets total")
```

!!! tip "page_size"
    Default is `50` (GLPI's own default). Increase to `100` or `200` for
    faster bulk exports on fast networks. Decrease if responses are slow or
    memory is constrained.

---

## iter_pages

Yields one page at a time — process each batch immediately without loading
everything into RAM:

```python
total = 0
for page in api.ticket.iter_pages(page_size=100):
    for ticket in page:
        process(ticket)
        total += 1

print(f"Processed {total} tickets")
```

Useful for:

- Very large datasets (tens of thousands of items)
- Streaming results to a database or file
- Progress reporting

---

## Async

Both methods work identically with `AsyncGlpiAPI` and `AsyncGlpiOAuthClient`:

```python
# All pages at once
tickets = await api.ticket.get_all_pages()

# Page by page
async for page in api.ticket.iter_pages(page_size=100):
    for ticket in page:
        await process(ticket)
```

---

## Low-level methods

If you need manual control over pagination, use the underlying methods directly:

```python
# Explicit range — single page
page1 = api.ticket.get_all(range="0-49")
page2 = api.ticket.get_all(range="50-99")

# Direct method on the client (same thing)
page1 = api.get_all_items("Ticket", range="0-49")
```

---

## How it works

1. Sends `GET /apirest.php/Ticket?range=0-49`
2. Reads `Content-Range: 0-49/1337` from the response header → knows total is 1337
3. Requests `50-99`, `100-149`, … until all items are fetched
4. Falls back to stopping on a partial page if `Content-Range` is absent
   (some GLPI versions omit it)
