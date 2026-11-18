from fastapi import APIRouter, Request, status
from app.api.v1.endpoints.operator_cinemas import AUDITORIUMS_STORE, LAYOUTS_STORE
from app.core.errors import APIException
from app.schemas.auditorium import AuditoriumLayoutResponse, LayoutSeatItem, ScreenMetadataSchema
from app.schemas.common import ResponseMeta, StandardResponse

router = APIRouter(prefix="/auditoriums", tags=["Auditorium Public Visualizer"])


@router.get("/{auditorium_id}/layout", response_model=StandardResponse[AuditoriumLayoutResponse])
async def get_auditorium_layout(auditorium_id: str, request: Request):
    """
    Public visualizer endpoint: returns the active published layout version,
    screen geometry, rows, physical seats, eye-points, and 3D object transforms.
    """
    request_id = getattr(request.state, "request_id", None)
    auditorium = AUDITORIUMS_STORE.get(auditorium_id)

    if not auditorium:
        raise APIException(
            code="AUDITORIUM_NOT_FOUND",
            message=f"Auditorium '{auditorium_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    version = auditorium.get("active_layout_version", 1)
    layout_id = f"lay-{auditorium_id}-v{version}"
    layout = LAYOUTS_STORE.get(layout_id)

    if not layout:
        # Fallback to any published version for this auditorium
        layout = next(
            (l for l in LAYOUTS_STORE.values() if l["auditorium_id"] == auditorium_id and l["status"] == "PUBLISHED"),
            None,
        )

    if not layout:
        raise APIException(
            code="NO_PUBLISHED_LAYOUT",
            message=f"No published layout version exists for auditorium '{auditorium_id}'.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return StandardResponse(
        data=AuditoriumLayoutResponse(
            layout_id=layout["layout_id"],
            auditorium_id=layout["auditorium_id"],
            version=layout["version"],
            status=layout["status"],
            screen=ScreenMetadataSchema(**layout["screen"]),
            geometry_metadata=layout["geometry_metadata"],
            seats=[LayoutSeatItem(**s) for s in layout["seats"]],
            published_at=layout["published_at"],
        ),
        meta=ResponseMeta(request_id=request_id),
    )
