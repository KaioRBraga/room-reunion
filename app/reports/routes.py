from datetime import datetime, timedelta

from flask import jsonify, render_template, request

from app.auth.decorators import report_access_required
from app.models import Room
from app.reports import reports_bp
from app.reports.services import build_report


def _month_range(today):
    start = today.replace(day=1)
    next_month = start.month + 1
    next_year = start.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    end = start.replace(year=next_year, month=next_month)
    return start, end


def _resolve_period(args):
    period = args.get("period", "month")
    today = datetime.now().date()

    if period == "week":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=7)
    elif period == "custom":
        start = datetime.strptime(args.get("start", ""), "%Y-%m-%d").date()
        end = datetime.strptime(args.get("end", ""), "%Y-%m-%d").date() + timedelta(days=1)
    else:
        start, end = _month_range(today)

    if end <= start:
        raise ValueError("Período inválido: data final deve ser depois da inicial.")

    return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.min.time())


@reports_bp.route("/")
@report_access_required
def dashboard():
    rooms = Room.query.order_by(Room.name).all()
    return render_template("reports/dashboard.html", rooms=rooms)


@reports_bp.route("/dados")
@report_access_required
def data():
    try:
        start_at, end_at = _resolve_period(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    room_id = request.args.get("room_id", type=int)
    return jsonify(build_report(start_at, end_at, room_id=room_id))
