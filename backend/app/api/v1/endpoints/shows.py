from typing import List, Optional
from fastapi import APIRouter, Request, status
from app.api.v1.endpoints.operator_shows import SHOWS_STORE
from app.core.errors import APIException
from app.schemas.common import ResponseMeta, StandardResponse
from app.schemas.show import ShowDetailResponse

router = APIRouter(prefix="/shows", tags=["Public Shows Discovery"])


@router.get("", response_model=StandardResponse[List[ShowDetailResponse]])
async def list_public_shows(
    request: Request,
    cinema_id: Optional[str] = None,
    movie_id: Optional[str] = None,
):
    request_id = getattr(request.state, "request_id", None)
    published_shows = [
        ShowDetailResponse(**s)
        for s in SHOWS_STORE.values()
        if s["status"] == "PUBLISHED"
        and (not cinema_id or s["cinema_id"] == cinema_id)
        and (not movie_id or s["movie_id"] == movie_id)
    ]

    return StandardResponse(
        data=published_shows,
        meta=ResponseMeta(request_id=request_id, total=len(published_shows)),
    )


@router.get("/{show_id}", response_model=StandardResponse[ShowDetailResponse])
async def get_show_details(show_id: str, request: Request):
    request_id = getattr(request.state, "request_id", None)
    show = SHOWS_STORE.get(show_id)

    if not show or show["status"] != "PUBLISHED":
        raise APIException(
            code="SHOW_NOT_FOUND",
            message=f"Show '{show_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return StandardResponse(
        data=ShowDetailResponse(**show),
        meta=ResponseMeta(request_id=request_id),
    )
