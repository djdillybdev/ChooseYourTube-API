import re
from datetime import datetime
from typing import Literal, Any
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.video import Video
from ..models.association_tables import video_tags
from ...schemas.video import VideoCreate
from .crud_base import (
    base_get,
    base_update,
    _validate_pagination,
    _validate_order_by_field,
    _validate_filter_field,
)

RELEVANCE_ORDER_BY = "relevance"


def _apply_video_ordering(query, order_column, order_by: str, order_direction: str):
    """Handle special nullslast logic for published_at ordering."""
    if order_direction == "desc":
        if order_by == "published_at":
            return query.order_by(order_column.desc().nullslast())
        else:
            return query.order_by(order_column.desc())
    else:
        return query.order_by(order_column.asc())


def _get_dialect_name(db: AsyncSession) -> str | None:
    """Get the dialect name from the session's bind."""
    if getattr(db, "bind", None) is not None:
        dialect = getattr(db.bind, "dialect", None)
        if dialect is not None:
            return getattr(dialect, "name", None)
    return None


def _build_prefix_tsquery(q: str) -> str:
    """Sanitize user input and build a prefix-matching tsquery string.

    Strips non-alphanumeric chars (except hyphens and whitespace), splits into
    words, and joins as "word1:* & word2:*" for prefix matching.

    Example: "pyth tuto" → "pyth:* & tuto:*"
    """
    sanitized = re.sub(r"[^\w\s-]", "", q, flags=re.UNICODE)
    words = sanitized.split()
    if not words:
        return ""
    return " & ".join(f"{word}:*" for word in words)


def _build_search_conditions(q: str, dialect_name: str | None):
    """Build search conditions for video title/description and tag name search.

    Returns a tuple of (video_text_condition, tag_name_condition, rank_expr).
    - video_text_condition: matches against Video.title and Video.description
    - tag_name_condition: matches against Tag.name (requires JOIN)
    - rank_expr: ts_rank expression for PostgreSQL, None for SQLite
    """
    from ..models.tag import Tag

    rank_expr = None

    if dialect_name == "postgresql":
        tsvector = func.to_tsvector(
            "english",
            Video.title + " " + func.coalesce(Video.description, ""),
        )
        prefix_query = _build_prefix_tsquery(q)
        if prefix_query:
            tsquery = func.to_tsquery("english", prefix_query)
        else:
            tsquery = func.plainto_tsquery("english", q)
        video_cond = tsvector.op("@@")(tsquery)
        rank_expr = func.ts_rank(tsvector, tsquery)
    else:
        # SQLite fallback: LIKE-based search (already supports substring/prefix)
        pattern = f"%{q.lower()}%"
        video_cond = or_(
            func.lower(Video.title).like(pattern),
            func.lower(func.coalesce(Video.description, "")).like(pattern),
        )

    # Tag name search: always ILIKE/LIKE
    tag_pattern = f"%{q.lower()}%"
    tag_cond = func.lower(Tag.name).like(tag_pattern)

    return video_cond, tag_cond, rank_expr


def _has_extended_filters(
    tag_id: str | None,
    published_after: datetime | None,
    published_before: datetime | None,
    q: str | None,
) -> bool:
    """Check if any extended filters are active."""
    return any([tag_id, published_after, published_before, q])


def _apply_extended_filters(
    query,
    db: AsyncSession,
    filters: dict[str, Any],
    tag_id: str | None,
    published_after: datetime | None,
    published_before: datetime | None,
    q: str | None,
):
    """Apply standard filters, JOINs, search, and date filters to a query.

    Returns a tuple of (query, rank_expr) where rank_expr is a ts_rank
    expression for PostgreSQL or None for SQLite/no search.
    """
    from ..models.tag import Tag

    dialect_name = _get_dialect_name(db)
    rank_expr = None

    # Apply standard column filters
    for field_name, value in filters.items():
        column = getattr(Video, field_name)
        if isinstance(value, (list, tuple)):
            query = query.where(column.in_(value))
        else:
            query = query.where(column == value)

    # tag_id filter: INNER JOIN video_tags
    if tag_id is not None:
        query = query.join(video_tags, Video.id == video_tags.c.video_id).where(
            video_tags.c.tag_id == tag_id
        )

    # Search: text search OR tag name search
    if q:
        video_cond, tag_cond, rank_expr = _build_search_conditions(q, dialect_name)
        if tag_id is not None:
            search_vt = video_tags.alias("search_vt")
            query = (
                query.outerjoin(search_vt, Video.id == search_vt.c.video_id)
                .outerjoin(Tag, search_vt.c.tag_id == Tag.id)
                .where(or_(video_cond, tag_cond))
            )
        else:
            query = (
                query.outerjoin(video_tags, Video.id == video_tags.c.video_id)
                .outerjoin(Tag, video_tags.c.tag_id == Tag.id)
                .where(or_(video_cond, tag_cond))
            )

    # Date range filters
    if published_after is not None:
        query = query.where(Video.published_at >= published_after)
    if published_before is not None:
        query = query.where(Video.published_at <= published_before)

    return query, rank_expr


async def create_videos_bulk(
    db_session: AsyncSession, videos_to_create: list[VideoCreate]
) -> None:
    """
    Bulk inserts video records using PostgreSQL's "ON CONFLICT DO NOTHING".
    This is highly efficient for adding many videos at once and safely
    handles duplicates without raising an error.
    """
    if not videos_to_create:
        return

    # Convert Pydantic models to dictionaries for the insert statement
    video_dicts = [video.model_dump() for video in videos_to_create]

    # Ensure `yt_tags` is a JSON-serializable list for DB storage.
    # The `Video.yt_tags` column uses JSON storage, so passing plain
    # Python lists works across SQLite and Postgres JSON types.
    for vd in video_dicts:
        if "yt_tags" in vd and vd["yt_tags"] is not None:
            if not isinstance(vd["yt_tags"], (list, tuple)):
                vd["yt_tags"] = [vd["yt_tags"]]

    # Create the bulk insert statement. Use the dialect-specific insert
    # constructor so we can call `on_conflict_do_nothing()` on both
    # Postgres and SQLite engines.
    dialect_name = _get_dialect_name(db_session)

    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert

        stmt = dialect_insert(Video).values(video_dicts)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
    else:
        # Default to Postgres-style insert which supports ON CONFLICT
        from sqlalchemy.dialects.postgresql import insert as dialect_insert

        stmt = dialect_insert(Video).values(video_dicts)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])

    await db_session.execute(stmt)
    await db_session.commit()


async def get_videos(
    db: AsyncSession,
    *,
    # Explicit parameters for common filters
    id: str | list[str] | None = None,
    channel_id: str | list[str] | None = None,
    is_favorited: bool | None = None,
    is_short: bool | None = None,
    is_watched: bool | None = None,
    # Extended filters
    tag_id: str | None = None,
    published_after: datetime | None = None,
    published_before: datetime | None = None,
    q: str | None = None,
    # Pagination
    limit: int | None = None,
    offset: int = 0,
    # Ordering
    order_by: str = "published_at",
    order_direction: Literal["asc", "desc"] = "desc",
    # Return type control
    first: bool = False,
    # Catch-all for any other Video field
    **kwargs: Any,
) -> list[Video] | Video | None:
    """
    Retrieve videos with flexible filtering, pagination, and ordering.

    Args:
        id: Single video ID or list of video IDs for IN clause
        channel_id: Single channel ID or list of channel IDs for IN clause
        is_favorited: Filter by favorited status
        is_short: Filter by YouTube Shorts
        is_watched: Filter by watched status
        tag_id: Filter by tag ID (SQL JOIN, not post-filter)
        published_after: Filter videos published on or after this datetime
        published_before: Filter videos published on or before this datetime
        q: Search query matching title, description, or tag names
        limit: Maximum number of results (None = unlimited)
        offset: Number of results to skip (for pagination)
        order_by: Field to order by
        order_direction: Sort direction ('asc' or 'desc')
        first: If True, return single Video or None instead of list
        **kwargs: Additional filter fields

    Returns:
        - If first=True: Single Video instance or None
        - If first=False: List of Video instances (empty list if no matches)
    """
    _validate_pagination(limit, offset)

    if order_direction not in ("asc", "desc"):
        raise ValueError("order_direction must be 'asc' or 'desc'")

    # Skip validation for the special "relevance" order_by value
    if order_by != RELEVANCE_ORDER_BY:
        _validate_order_by_field(Video, order_by)

    # Normalize empty search string to None
    if q is not None and q.strip() == "":
        q = None

    # If relevance requested without a search query, fall back to published_at
    if order_by == RELEVANCE_ORDER_BY and q is None:
        order_by = "published_at"

    filters = {}
    if id is not None:
        filters["id"] = id
    if channel_id is not None:
        filters["channel_id"] = channel_id
    if is_favorited is not None:
        filters["is_favorited"] = is_favorited
    if is_short is not None:
        filters["is_short"] = is_short
    if is_watched is not None:
        filters["is_watched"] = is_watched

    # Add any additional kwargs
    for key, value in kwargs.items():
        if value is not None:
            filters[key] = value

    for field_name in filters.keys():
        _validate_filter_field(Video, field_name)

    # Fast path: no extended filters, delegate to base_get
    if not _has_extended_filters(tag_id, published_after, published_before, q):
        return await base_get(
            db,
            Video,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            order_direction=order_direction,
            first=first,
            special_ordering_handler=_apply_video_ordering,
        )

    # Extended path: build query with JOINs
    query, rank_expr = _apply_extended_filters(
        select(Video), db, filters, tag_id, published_after, published_before, q
    )

    # Handle relevance ordering with rank expression
    use_relevance = order_by == RELEVANCE_ORDER_BY and rank_expr is not None

    if use_relevance:
        # PostgreSQL: use subquery to handle DISTINCT + ORDER BY rank
        rank_label = rank_expr.label("_rank")
        ranked_query, _ = _apply_extended_filters(
            select(Video, rank_label), db, filters, tag_id, published_after, published_before, q
        )
        # Use a subquery with GROUP BY Video.id to deduplicate
        # instead of DISTINCT, since we need to order by _rank
        ranked_query = ranked_query.group_by(Video.id)
        ranked_query = ranked_query.order_by(func.max(rank_label).desc())

        # Apply pagination
        if limit is not None:
            ranked_query = ranked_query.limit(limit)
        ranked_query = ranked_query.offset(offset)

        result = await db.execute(ranked_query)
        rows = result.all()

        if first:
            return rows[0][0] if rows else None
        return [row[0] for row in rows]

    # DISTINCT to deduplicate from JOINs
    query = query.distinct()

    # Fall back to published_at for relevance on SQLite
    effective_order_by = "published_at" if order_by == RELEVANCE_ORDER_BY else order_by
    order_column = getattr(Video, effective_order_by)
    query = _apply_video_ordering(query, order_column, effective_order_by, order_direction)

    # Apply pagination
    if limit is not None:
        query = query.limit(limit)
    query = query.offset(offset)

    result = await db.execute(query)

    if first:
        return result.scalars().first()
    else:
        return list(result.unique().scalars().all())


async def count_videos(
    db: AsyncSession,
    *,
    # Explicit parameters for common filters
    id: str | list[str] | None = None,
    channel_id: str | list[str] | None = None,
    is_favorited: bool | None = None,
    is_short: bool | None = None,
    is_watched: bool | None = None,
    # Extended filters
    tag_id: str | None = None,
    published_after: datetime | None = None,
    published_before: datetime | None = None,
    q: str | None = None,
    # Catch-all for any other Video field
    **kwargs: Any,
) -> int:
    """
    Count videos matching the given filters.

    Args:
        id: Single video ID or list of video IDs for IN clause
        channel_id: Single channel ID or list of channel IDs for IN clause
        is_favorited: Filter by favorited status
        is_short: Filter by YouTube Shorts
        is_watched: Filter by watched status
        tag_id: Filter by tag ID (SQL JOIN)
        published_after: Filter videos published on or after this datetime
        published_before: Filter videos published on or before this datetime
        q: Search query matching title, description, or tag names
        **kwargs: Additional filter fields

    Returns:
        Total count of videos matching the filters
    """
    # Normalize empty search string to None
    if q is not None and q.strip() == "":
        q = None

    filters = {}
    if id is not None:
        filters["id"] = id
    if channel_id is not None:
        filters["channel_id"] = channel_id
    if is_favorited is not None:
        filters["is_favorited"] = is_favorited
    if is_short is not None:
        filters["is_short"] = is_short
    if is_watched is not None:
        filters["is_watched"] = is_watched

    # Add any additional kwargs
    for key, value in kwargs.items():
        if value is not None:
            filters[key] = value

    for field_name in filters.keys():
        _validate_filter_field(Video, field_name)

    # Simple path: no extended filters
    if not _has_extended_filters(tag_id, published_after, published_before, q):
        query = select(func.count()).select_from(Video)
        for field_name, value in filters.items():
            column = getattr(Video, field_name)
            if isinstance(value, list):
                query = query.where(column.in_(value))
            else:
                query = query.where(column == value)
        result = await db.execute(query)
        return result.scalar() or 0

    # Extended path: use COUNT(DISTINCT video.id) with same JOINs
    count_query, _ = _apply_extended_filters(
        select(func.count(func.distinct(Video.id))).select_from(Video),
        db, filters, tag_id, published_after, published_before, q,
    )
    result = await db.execute(count_query)
    return result.scalar() or 0


async def update_video(db: AsyncSession, video: Video) -> Video:
    """
    Updates a video instance in the database.

    Args:
        db: Database session
        video: The video instance with modified attributes

    Returns:
        The refreshed video instance
    """
    return await base_update(db, video)


async def delete_video(db_session: AsyncSession, video_to_delete: Video) -> None:
    """
    Deletes a specific video instance from the database.

    Args:
        db_session: Database session
        video_to_delete: The video instance to delete
    """
    await db_session.delete(video_to_delete)
    await db_session.commit()
