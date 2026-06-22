from collections import defaultdict

from app.models import Booking, Room


def _business_hours_per_day(room):
    """Horas de expediente da sala, ou None se a sala não tem janela definida."""
    if room.business_hours_start is None or room.business_hours_end is None:
        return None
    start = room.business_hours_start
    end = room.business_hours_end
    start_seconds = start.hour * 3600 + start.minute * 60 + start.second
    end_seconds = end.hour * 3600 + end.minute * 60 + end.second
    return max(end_seconds - start_seconds, 0) / 3600


def build_report(start_at, end_at, room_id=None):
    """Agrega as reservas de `start_at` (inclusive) a `end_at` (exclusive)."""
    rooms = Room.query.order_by(Room.name).all()
    if room_id is not None:
        rooms = [r for r in rooms if r.id == room_id]
    rooms_by_id = {r.id: r for r in rooms}

    if not rooms_by_id:
        bookings = []
    else:
        bookings = Booking.query.filter(
            Booking.room_id.in_(rooms_by_id.keys()),
            Booking.start_at < end_at,
            Booking.end_at > start_at,
        ).all()

    active = [b for b in bookings if b.is_active]
    cancelled = [b for b in bookings if not b.is_active]
    no_show = [b for b in cancelled if b.cancelled_by == "auto:no-show"]
    days = max((end_at - start_at).total_seconds() / 86400, 0)

    by_room = defaultdict(lambda: {"bookings_count": 0, "occupied_hours": 0.0})
    organizers = defaultdict(lambda: {"bookings_count": 0, "display_name": ""})
    durations_minutes = []
    early_started = []

    for booking in active:
        clipped_start = max(booking.start_at, start_at)
        clipped_end = min(booking.end_at, end_at)
        occupied_hours = max((clipped_end - clipped_start).total_seconds() / 3600, 0)
        durations_minutes.append((booking.end_at - booking.start_at).total_seconds() / 60)

        room_stats = by_room[booking.room_id]
        room_stats["bookings_count"] += 1
        room_stats["occupied_hours"] += occupied_hours

        org_stats = organizers[booking.organizer_username]
        org_stats["bookings_count"] += 1
        org_stats["display_name"] = booking.organizer_display_name or booking.organizer_username

        if booking.checked_in_at is not None and booking.checked_in_at < booking.start_at:
            early_started.append(booking)

    by_room_list = []
    for room in rooms:
        stats = by_room.get(room.id, {"bookings_count": 0, "occupied_hours": 0.0})
        hours_per_day = _business_hours_per_day(room)
        available_hours = hours_per_day * days if hours_per_day is not None else None
        occupancy_rate = (
            round(stats["occupied_hours"] / available_hours * 100, 1)
            if available_hours
            else None
        )
        by_room_list.append(
            {
                "room_id": room.id,
                "room_name": room.name,
                "bookings_count": stats["bookings_count"],
                "occupied_hours": round(stats["occupied_hours"], 1),
                "occupancy_rate": occupancy_rate,
            }
        )

    by_organizer_list = sorted(
        (
            {
                "username": username,
                "display_name": data["display_name"],
                "bookings_count": data["bookings_count"],
            }
            for username, data in organizers.items()
        ),
        key=lambda o: o["bookings_count"],
        reverse=True,
    )

    avg_duration = round(sum(durations_minutes) / len(durations_minutes), 1) if durations_minutes else None
    no_show_rate = round(len(no_show) / len(bookings) * 100, 1) if bookings else None

    return {
        "period": {"start": start_at.isoformat(), "end": end_at.isoformat()},
        "totals": {
            "bookings_count": len(active),
            "cancelled_count": len(cancelled),
            "no_show_count": len(no_show),
            "no_show_rate": no_show_rate,
            "avg_duration_minutes": avg_duration,
        },
        "by_room": by_room_list,
        "by_organizer": by_organizer_list,
        "busiest_room": max(by_room_list, key=lambda r: r["bookings_count"]) if by_room_list else None,
        "quietest_room": min(by_room_list, key=lambda r: r["bookings_count"]) if by_room_list else None,
        "top_organizer": by_organizer_list[0] if by_organizer_list else None,
        "bottom_organizer": by_organizer_list[-1] if by_organizer_list else None,
        "early_started_meetings": [
            {
                "id": b.id,
                "title": b.title,
                "room_name": rooms_by_id[b.room_id].name,
                "scheduled_start": b.start_at.isoformat(),
                "actual_start": b.checked_in_at.isoformat(),
            }
            for b in early_started
        ],
    }
