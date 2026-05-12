"""
Generic base repository providing async CRUD operations for SQLAlchemy models.

All public methods are async and require an AsyncSession. Soft-delete behaviour
is guarded with ``hasattr`` so the class works safely with models that do not
define a ``deleted_at`` column.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from sqlalchemy import func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect

from app.utils.logging import get_logger

logger = get_logger(__name__)

# Unbound TypeVar — not all existing models inherit from Base yet.
ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Generic async repository with CRUD, filtering, and optional soft-delete.

    Soft-delete operations are only available when the model declares a
    ``deleted_at`` column (i.e. ``hasattr(model, "deleted_at")`` is True).
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession) -> None:
        """
        Initialise the repository with a model class and an async session.

        Args:
            model: The SQLAlchemy ORM model class this repository manages.
            session: An open ``AsyncSession`` to execute queries against.
        """
        self.model = model
        self.session = session
        # Convenience alias used by some callers.
        self.db = session

        # Operator map used by _apply_filters.
        self.operators: Dict[str, Any] = {
            "eq":        lambda col, val: col == val,
            "ne":        lambda col, val: col != val,
            "gt":        lambda col, val: col > val,
            "lt":        lambda col, val: col < val,
            "gte":       lambda col, val: col >= val,
            "lte":       lambda col, val: col <= val,
            "like":      lambda col, val: col.like(f"%{val}%"),
            "icontains": lambda col, val: col.ilike(f"%{val}%"),
            "in_":       lambda col, val: col.in_(val),
            "not_in":    lambda col, val: ~col.in_(val),
        }

        model_name = getattr(model, "__name__", str(model))
        logger.debug("Initialised %s for %s", self.__class__.__name__, model_name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _has_soft_delete(self) -> bool:
        """Return True if the model declares a ``deleted_at`` column."""
        return hasattr(self.model, "deleted_at")

    def _apply_soft_delete_filter(self, query: Any, include_deleted: bool) -> Any:
        """
        Append a ``deleted_at IS NULL`` clause when appropriate.

        If the model has no ``deleted_at`` column the query is returned
        unchanged (behaves as ``include_deleted=True``).
        """
        if not include_deleted and self._has_soft_delete():
            query = query.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return query

    def _apply_filters(self, query: Any, filters: Dict[str, Any]) -> Any:
        """
        Apply a flexible filter dict to a SQLAlchemy query.

        Supported syntax examples::

            {"name__icontains": "abc"}          # double-underscore operator
            {"price": {"gte": 100, "lte": 200}} # dict of {operator: value}
            {"id": 5}                            # exact equality shorthand

        Recognised operators: eq, ne, gt, lt, gte, lte, like, icontains,
        in_, not_in.
        """
        conditions: List[Any] = []

        for key, value in filters.items():
            if "__" in key:
                # e.g. "name__icontains" -> field="name", op="icontains"
                parts = key.split("__")
                field_name = "__".join(parts[:-1])
                operator = parts[-1]
                if hasattr(self.model, field_name):
                    op_fn = self.operators.get(operator, self.operators["eq"])
                    conditions.append(op_fn(getattr(self.model, field_name), value))
                else:
                    logger.warning(
                        "Filter field '%s' not found on %s — skipped",
                        field_name, self.model.__name__,
                    )
            elif isinstance(value, dict):
                # e.g. {"price": {"gte": 100}}
                for op, val in value.items():
                    if op in self.operators and hasattr(self.model, key):
                        conditions.append(self.operators[op](getattr(self.model, key), val))
            elif hasattr(self.model, key):
                # Exact equality shorthand
                conditions.append(self.operators["eq"](getattr(self.model, key), value))
            else:
                logger.warning(
                    "Filter key '%s' not found on %s — skipped",
                    key, self.model.__name__,
                )

        if conditions:
            query = query.where(*conditions)
        return query

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get(
        self,
        id: Union[int, UUID, str],
        *,
        options: Optional[List[Any]] = None,
        include_deleted: bool = False,
    ) -> Optional[ModelType]:
        """
        Retrieve a single record by primary key.

        Returns ``None`` if not found or (when ``include_deleted=False``) if
        the record has been soft-deleted.
        """
        query = select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        query = self._apply_soft_delete_filter(query, include_deleted)
        if options:
            query = query.options(*options)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        id: Union[int, UUID, str],
        *,
        include_deleted: bool = False,
    ) -> Optional[ModelType]:
        """Convenience alias for :meth:`get`."""
        return await self.get(id=id, include_deleted=include_deleted)

    async def get_by_field(
        self,
        field: str,
        value: Any,
        *,
        options: Optional[List[Any]] = None,
        include_deleted: bool = False,
    ) -> Optional[ModelType]:
        """
        Retrieve the first record whose ``field`` equals ``value``.

        Returns ``None`` when the field does not exist on the model or no
        matching row is found.
        """
        if not hasattr(self.model, field):
            logger.warning(
                "get_by_field: field '%s' not found on %s", field, self.model.__name__
            )
            return None

        query = select(self.model).where(getattr(self.model, field) == value)
        query = self._apply_soft_delete_filter(query, include_deleted)
        if options:
            query = query.options(*options)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        options: Optional[List[Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[Any] = None,
        include_deleted: bool = False,
    ) -> List[ModelType]:
        """
        Retrieve a paginated, optionally filtered list of records.

        ``filters`` uses the same syntax as :meth:`_apply_filters`.
        """
        query = select(self.model)
        query = self._apply_soft_delete_filter(query, include_deleted)

        if filters:
            query = self._apply_filters(query, filters)
        if order_by is not None:
            query = query.order_by(order_by)
        if options:
            query = query.options(*options)
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        options: Optional[List[Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        include_deleted: bool = False,
        **extra_filters: Any,
    ) -> List[ModelType]:
        """
        Retrieve records, merging ``filters`` dict with keyword ``extra_filters``.

        ``extra_filters`` are treated as exact-equality filters and merged
        with (and override) the ``filters`` dict before delegating to
        :meth:`get_multi`.
        """
        combined: Dict[str, Any] = dict(filters) if filters else {}
        combined.update(extra_filters)
        return await self.get_multi(
            skip=skip,
            limit=limit,
            options=options,
            filters=combined or None,
            include_deleted=include_deleted,
        )

    async def count(
        self,
        *,
        filters: Optional[Dict[str, Any]] = None,
        include_deleted: bool = False,
    ) -> int:
        """
        Return the count of records matching the given filters.

        Soft-deleted records are excluded unless ``include_deleted=True``.
        """
        query = select(func.count()).select_from(self.model)
        query = self._apply_soft_delete_filter(query, include_deleted)
        if filters:
            query = self._apply_filters(query, filters)

        result = await self.session.execute(query)
        return result.scalar() or 0

    async def create(
        self,
        *,
        obj_in: Union[Any, Dict[str, Any], None] = None,
        commit: bool = False,
        **kwargs: Any,
    ) -> ModelType:
        """
        Persist a new record from a Pydantic model, dict, or keyword arguments.

        Relationship keys reported by the mapper are stripped automatically to
        avoid assignment errors. Flushes by default; commits when
        ``commit=True``.
        """
        try:
            if obj_in is None:
                obj_in_data: Dict[str, Any] = kwargs
            elif hasattr(obj_in, "model_dump"):
                # Pydantic v2
                obj_in_data = obj_in.model_dump()
            elif hasattr(obj_in, "dict"):
                # Pydantic v1
                obj_in_data = obj_in.dict()
            elif isinstance(obj_in, dict):
                obj_in_data = obj_in
            else:
                # Last resort: convert via __dict__ stripping SQLAlchemy state
                obj_in_data = {
                    k: v
                    for k, v in vars(obj_in).items()
                    if not k.startswith("_")
                }

            # Strip relationship keys to avoid SQLAlchemy assignment errors.
            mapper = inspect(self.model)
            relationship_keys = {rel.key for rel in mapper.relationships}
            filtered_data = {
                k: v for k, v in obj_in_data.items() if k not in relationship_keys
            }

            db_obj: ModelType = self.model(**filtered_data)
            self.session.add(db_obj)

            if commit:
                await self.session.commit()
            else:
                await self.session.flush()

            await self.session.refresh(db_obj)
            logger.info(
                "Created %s id=%s",
                self.model.__name__,
                getattr(db_obj, "id", "?"),
            )
            return db_obj
        except Exception:
            if commit:
                await self.session.rollback()
            raise

    async def update(
        self,
        *,
        db_obj: ModelType,
        obj_in: Union[Any, Dict[str, Any], None] = None,
        commit: bool = False,
        **kwargs: Any,
    ) -> ModelType:
        """
        Update ``db_obj`` with data from a Pydantic model, dict, or kwargs.

        Relationship keys are skipped; all other matching attributes are set
        via ``setattr``. Flushes by default; commits when ``commit=True``.
        """
        try:
            if obj_in is None:
                update_data: Dict[str, Any] = kwargs
            elif hasattr(obj_in, "model_dump"):
                update_data = obj_in.model_dump(exclude_unset=True)
            elif hasattr(obj_in, "dict"):
                update_data = obj_in.dict(exclude_unset=True)
            elif isinstance(obj_in, dict):
                update_data = obj_in
            else:
                update_data = vars(obj_in)

            mapper = inspect(self.model)
            relationship_keys = {rel.key for rel in mapper.relationships}
            column_keys = [col.key for col in mapper.columns]

            for field, value in update_data.items():
                if field not in relationship_keys and hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            self.session.add(db_obj)

            if commit:
                await self.session.commit()
            else:
                await self.session.flush()

            await self.session.refresh(db_obj, attribute_names=column_keys)
            logger.info(
                "Updated %s id=%s",
                self.model.__name__,
                getattr(db_obj, "id", "?"),
            )
            return db_obj
        except Exception:
            if commit:
                await self.session.rollback()
            raise

    async def delete(
        self,
        id: Union[int, UUID, str],
        *,
        soft: bool = True,
        commit: bool = False,
    ) -> Optional[ModelType]:
        """
        Delete a record by primary key.

        With ``soft=True`` (default): sets ``deleted_at`` to the current UTC
        time.  Raises ``AttributeError`` when ``soft=True`` but the model has
        no ``deleted_at`` column.

        With ``soft=False``: issues a hard ``DELETE`` via the session.

        Returns ``None`` when no record with the given ``id`` exists.
        """
        # For soft delete we want to find even already-soft-deleted rows so
        # callers can "re-delete" without getting None; for hard delete we
        # only fetch live rows.
        obj = await self.get(id=id, include_deleted=True)
        if obj is None:
            logger.warning(
                "delete: %s id=%s not found", self.model.__name__, id
            )
            return None

        if soft:
            if not self._has_soft_delete():
                raise AttributeError(
                    f"Model {self.model.__name__!r} does not have a 'deleted_at' "
                    "column. Use soft=False for a hard delete, or add "
                    "SoftDeleteMixin to the model."
                )
            if hasattr(obj, "soft_delete"):
                obj.soft_delete()  # type: ignore[union-attr]
            else:
                obj.deleted_at = datetime.now(tz=timezone.utc)  # type: ignore[attr-defined]
            self.session.add(obj)
        else:
            await self.session.delete(obj)

        if commit:
            await self.session.commit()
        else:
            await self.session.flush()

        if soft and obj in self.session:
            await self.session.refresh(obj)

        logger.info(
            "%s %s id=%s",
            "Soft-deleted" if soft else "Hard-deleted",
            self.model.__name__,
            id,
        )
        return obj

    async def exists(
        self,
        id: Union[int, UUID, str],
        *,
        include_deleted: bool = False,
    ) -> bool:
        """
        Return True if a record with the given primary key exists.

        Respects soft-delete unless ``include_deleted=True``.
        """
        instance = await self.get(id=id, include_deleted=include_deleted)
        return instance is not None
