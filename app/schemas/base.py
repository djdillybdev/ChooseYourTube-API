from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse[T](BaseModel):
    """
    Generic base schema for paginated responses.

    Usage:
        response_model=PaginatedResponse[ChannelOut]
        response_model=PaginatedResponse[VideoOut]
    """

    total: int
    items: list[T]
    limit: int
    offset: int
    has_more: bool
