from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from fpdf import FPDF

from sharetrip.api.dependencies import (
    get_trip_repository,
    get_user_repository,
    require_trip_member,
)
from sharetrip.api.schemas.expenses import TransferResponse
from sharetrip.use_cases.compute_settlements import (
    ComputeSettlementsInput,
    ComputeSettlementsUseCase,
)

router = APIRouter(prefix="/trips", tags=["Settlements"])


@router.get("/{trip_id}/settlements", response_model=list[TransferResponse])
def get_settlements(
    trip=Depends(require_trip_member),
    trip_repo=Depends(get_trip_repository),
):
    try:
        output = ComputeSettlementsUseCase(trip_repo).execute(
            ComputeSettlementsInput(trip_id=trip.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return [
        TransferResponse(
            from_user_id=t.from_user_id,
            to_user_id=t.to_user_id,
            amount=t.amount,
        )
        for t in output.transfers
    ]


@router.get("/{trip_id}/settlements/pdf")
def get_settlements_pdf(
    trip=Depends(require_trip_member),
    trip_repo=Depends(get_trip_repository),
    user_repo=Depends(get_user_repository),
):
    try:
        output = ComputeSettlementsUseCase(trip_repo).execute(
            ComputeSettlementsInput(trip_id=trip.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    expenses = trip_repo.list_expenses(trip.id)

    user_ids = (
        {t.from_user_id for t in output.transfers}
        | {t.to_user_id for t in output.transfers}
        | {e.paid_by for e in expenses}
    )
    users = {uid: user_repo.get_by_id(uid) for uid in user_ids}

    def display(uid: int) -> str:
        u = users.get(uid)
        return u.display_name if u else f"User #{uid}"

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Trip: {trip.name}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Currency: {trip.base_currency}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(
        0,
        6,
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Settlements", new_x="LMARGIN", new_y="NEXT")
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 11)
    if output.transfers:
        for t in output.transfers:
            pdf.cell(
                0,
                7,
                f"  {display(t.from_user_id)}  ->  {display(t.to_user_id)} :  {t.amount:.2f} {trip.base_currency}",
                new_x="LMARGIN",
                new_y="NEXT",
            )
    else:
        pdf.set_font("Helvetica", "I", 11)
        pdf.cell(
            0,
            7,
            "  No settlements needed - everyone is even.",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Expenses", new_x="LMARGIN", new_y="NEXT")
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 11)
    if expenses:
        for e in expenses:
            label = f"  {e.title} - {e.amount_pivot:.2f} {trip.base_currency} (paid by {display(e.paid_by)})"
            if e.category:
                label += f"  [{e.category}]"
            pdf.cell(0, 7, label, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", "I", 11)
        pdf.cell(0, 7, "  No expenses recorded.", new_x="LMARGIN", new_y="NEXT")

    pdf_bytes = bytes(pdf.output())
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=sharetrip_trip_{trip.id}.pdf"
        },
    )
