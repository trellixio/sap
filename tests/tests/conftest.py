import typing

from beanie import PydanticObjectId
from fastapi import HTTPException
from fastapi import status as http_status

from AppMain.asgi import app
from sap.fastapi import Object404Error
from tests.samples import DummyDoc


# Test endpoints for REST helper testing
@app.get("/test/items/")
async def test_list_items() -> dict[str, typing.Any]:
    """Test list endpoint."""
    return {"data": [{"id": "123", "name": "Test Item"}]}


@app.get("/test/items/{item_id}/")
async def api_retrieve_item(item_id: str) -> dict[str, typing.Any]:
    """Test retrieve endpoint."""
    return {"id": item_id, "name": "Test Item", "value": 100}


@app.post("/test/items/", status_code=http_status.HTTP_201_CREATED)
async def api_create_item(data: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Test create endpoint."""
    if not isinstance(data.get("status"), str):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"loc": ["body", "status"], "msg": "Invalid type"}],
        )
    return data


@app.put("/test/items/{item_id}/", status_code=http_status.HTTP_202_ACCEPTED)
async def api_update_item(item_id: str, data: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Test update endpoint."""
    if not isinstance(data.get("name"), str):
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"loc": ["body", "name"], "msg": "Invalid type"}],
        )
    data["id"] = item_id
    return data


@app.delete("/test/items/{item_id}/", status_code=http_status.HTTP_204_NO_CONTENT)
async def api_delete_item(item_id: str) -> None:
    """Test delete endpoint."""
    # For real integration, delete from DB if document exists
    try:
        doc = await DummyDoc.get_or_404(PydanticObjectId(item_id))
    except (Object404Error, ValueError):
        pass  # Not a valid ID or doesn't exist, which is fine for testing
    else:
        await doc.delete()
