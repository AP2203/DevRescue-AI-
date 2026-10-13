"""Base MongoDB repository with common CRUD operations."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.core.object_id import to_object_id

logger = logging.getLogger(__name__)


def make_storable(doc: dict) -> dict:
    """Convert string/PyObjectId ID fields to bson ObjectIds for MongoDB storage.

    Document models serialize ids as strings; MongoDB expects ObjectId values so
    that lookups (which convert to ObjectId) match.
    """
    out = dict(doc)
    for key in list(out):
        if key == "_id" or str(key).endswith("_id"):
            value = out[key]
            if isinstance(value, str) and ObjectId.is_valid(value):
                out[key] = ObjectId(value)
    return out


class BaseRepository:
    collection_name: str = ""

    def __init__(self, db: Any) -> None:
        self.db = db
        self.collection: AsyncIOMotorCollection = db[self.collection_name]

    # ---- create ----
    async def insert_one(self, document: dict) -> dict:
        document = make_storable(document)
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def replace_by_id(self, document: dict) -> dict:
        document = make_storable(document)
        _id = document["_id"]
        await self.collection.replace_one({"_id": _id}, document, upsert=True)
        return document

    # ---- read ----
    async def find_by_id(self, record_id: ObjectId | str) -> Optional[dict]:
        oid = to_object_id(record_id)
        return await self.collection.find_one({"_id": oid})

    async def find_one(self, query: Dict[str, Any]) -> Optional[dict]:
        return await self.collection.find_one(query)

    async def find_many(
        self,
        query: Dict[str, Any] = None,
        *,
        sort: Optional[List[Tuple[str, int]]] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[dict]:
        cursor = self.collection.find(query or {})
        if sort:
            cursor = cursor.sort(sort)
        return [doc async for doc in cursor.skip(skip).limit(limit)]

    async def count(self, query: Dict[str, Any] = None) -> int:
        return await self.collection.count_documents(query or {})

    async def exists(self, query: Dict[str, Any]) -> bool:
        return await self.collection.find_one(query, {"_id": 1}) is not None

    # ---- update ----
    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> Optional[dict]:
        doc = await self.collection.find_one_and_update(query, update, return_document=True, upsert=upsert)
        return doc

    async def update_by_id(self, record_id: ObjectId | str, fields: Dict[str, Any]) -> Optional[dict]:
        payload: Dict[str, Any] = {"$set": fields, "$setOnInsert": {}}
        return await self.update_one({"_id": to_object_id(record_id)}, payload)

    # ---- delete ----
    async def delete_by_id(self, record_id: ObjectId | str) -> bool:
        result = await self.collection.delete_one({"_id": to_object_id(record_id)})
        return result.deleted_count == 1

    async def delete_many(self, query: Dict[str, Any]) -> int:
        result = await self.collection.delete_many(query)
        return result.deleted_count

    async def aggregate(self, pipeline: List[dict]) -> List[dict]:
        return [doc async for doc in self.collection.aggregate(pipeline)]
