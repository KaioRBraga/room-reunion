from datetime import datetime

import pytest

from app import create_app
from app.bookings.services import cancel_booking, create_booking
from app.extensions import db
from app.models import ReportViewerGroup, Room
from app.reports.services import build_report
from config import TestConfig


@pytest.fixture
def app():
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def room(app):
    room = Room(name="Sala Relatório", capacity=6)
    db.session.add(room)
    db.session.commit()
    return room


# --- Permissão de visualização (global, diferente da de agendamento por sala) ---


def test_report_with_no_groups_is_admin_only(app):
    assert ReportViewerGroup.can_view([], is_admin=True)
    assert not ReportViewerGroup.can_view([], is_admin=False)
    assert not ReportViewerGroup.can_view(["qualquer_grupo"], is_admin=False)


def test_report_allows_user_in_allowed_group(app):
    db.session.add(ReportViewerGroup(group_cn="g_diretoria"))
    db.session.commit()

    assert ReportViewerGroup.can_view(["g_diretoria"], is_admin=False)
    assert not ReportViewerGroup.can_view(["g_outro"], is_admin=False)


def test_report_always_allows_admin_even_with_groups_configured(app):
    db.session.add(ReportViewerGroup(group_cn="g_diretoria"))
    db.session.commit()

    assert ReportViewerGroup.can_view([], is_admin=True)


# --- Agregação de métricas ---


def test_build_report_aggregates_metrics(app, room):
    period_start = datetime(2026, 1, 5)
    period_end = datetime(2026, 1, 12)

    booking_1 = create_booking(
        room.id, "Reunião 1", "ana", "Ana Souza", datetime(2026, 1, 6, 9), datetime(2026, 1, 6, 10)
    )
    create_booking(
        room.id, "Reunião 2", "ana", "Ana Souza", datetime(2026, 1, 7, 9), datetime(2026, 1, 7, 10)
    )
    create_booking(
        room.id, "Reunião 3", "bruno", "Bruno Lima", datetime(2026, 1, 8, 14), datetime(2026, 1, 8, 14, 30)
    )
    no_show = create_booking(
        room.id, "Reunião 4", "bruno", "Bruno Lima", datetime(2026, 1, 9, 9), datetime(2026, 1, 9, 9, 30)
    )
    cancel_booking(no_show.id, "auto:no-show")

    # Check-in antecipado: começou antes do horário marcado.
    booking_1.checked_in_at = datetime(2026, 1, 6, 8, 50)
    db.session.commit()

    report = build_report(period_start, period_end)

    assert report["totals"]["bookings_count"] == 3
    assert report["totals"]["cancelled_count"] == 1
    assert report["totals"]["no_show_count"] == 1

    assert report["top_organizer"]["username"] == "ana"
    assert report["top_organizer"]["bookings_count"] == 2
    assert report["bottom_organizer"]["username"] == "bruno"
    assert report["bottom_organizer"]["bookings_count"] == 1

    assert report["busiest_room"]["room_name"] == "Sala Relatório"
    assert report["busiest_room"]["bookings_count"] == 3

    assert len(report["early_started_meetings"]) == 1
    assert report["early_started_meetings"][0]["title"] == "Reunião 1"


def test_build_report_filters_by_room(app, room):
    other_room = Room(name="Outra sala", capacity=4)
    db.session.add(other_room)
    db.session.commit()

    create_booking(room.id, "Reunião 1", "ana", "Ana Souza", datetime(2026, 1, 6, 9), datetime(2026, 1, 6, 10))
    create_booking(
        other_room.id, "Reunião 2", "bruno", "Bruno Lima", datetime(2026, 1, 6, 9), datetime(2026, 1, 6, 10)
    )

    report = build_report(datetime(2026, 1, 5), datetime(2026, 1, 12), room_id=room.id)

    assert report["totals"]["bookings_count"] == 1
    assert len(report["by_room"]) == 1
    assert report["by_room"][0]["room_name"] == "Sala Relatório"


def test_build_report_with_no_bookings_returns_empty_metrics(app, room):
    report = build_report(datetime(2026, 1, 5), datetime(2026, 1, 12))

    assert report["totals"]["bookings_count"] == 0
    assert report["totals"]["no_show_rate"] is None
    assert report["top_organizer"] is None
    assert report["bottom_organizer"] is None
    assert report["early_started_meetings"] == []
