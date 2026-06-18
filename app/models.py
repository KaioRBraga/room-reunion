from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def localnow():
    # start_at/end_at das reservas são salvos em horário local (sem timezone),
    # então "agora" precisa ser comparado em horário local, não UTC.
    return datetime.now()


class Room(db.Model):
    __tablename__ = "room"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(200), nullable=True)
    equipment_notes = db.Column(db.Text, nullable=True)
    availability_notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # Posição relativa (0.0-1.0) do pin sobre a imagem do mapa atual.
    # None significa que a sala ainda não foi posicionada no mapa.
    pos_x = db.Column(db.Float, nullable=True)
    pos_y = db.Column(db.Float, nullable=True)

    # Token usado pelo painel/tablet da sala (app Android) para se autenticar
    # sem precisar de login AD. None = nenhum painel configurado ainda.
    display_token = db.Column(db.String(64), unique=True, nullable=True)

    bookings = db.relationship(
        "Booking", backref="room", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def is_on_map(self):
        return self.pos_x is not None and self.pos_y is not None

    def is_occupied_now(self):
        now = localnow()
        return (
            self.bookings.filter(
                Booking.cancelled_at.is_(None),
                Booking.start_at <= now,
                Booking.end_at > now,
            ).count()
            > 0
        )

    def current_booking(self, now=None):
        now = now or localnow()
        return (
            self.bookings.filter(
                Booking.cancelled_at.is_(None),
                Booking.start_at <= now,
                Booking.end_at > now,
            )
            .order_by(Booking.start_at)
            .first()
        )

    def next_booking(self, after=None):
        after = after or localnow()
        return (
            self.bookings.filter(
                Booking.cancelled_at.is_(None),
                Booking.start_at > after,
            )
            .order_by(Booking.start_at)
            .first()
        )

    def __repr__(self):
        return f"<Room {self.name}>"


class FloorMap(db.Model):
    __tablename__ = "floor_map"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_by = db.Column(db.String(120), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def __repr__(self):
        return f"<FloorMap {self.filename}>"


class Booking(db.Model):
    __tablename__ = "booking"
    __table_args__ = (
        db.CheckConstraint("end_at > start_at", name="ck_booking_end_after_start"),
        db.Index("ix_booking_room_time", "room_id", "start_at", "end_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    organizer_username = db.Column(db.String(120), nullable=False, index=True)
    organizer_display_name = db.Column(db.String(200), nullable=True)

    start_at = db.Column(db.DateTime, nullable=False, index=True)
    end_at = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancelled_by = db.Column(db.String(120), nullable=True)
    checked_in_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_active(self):
        return self.cancelled_at is None

    @classmethod
    def find_conflict(cls, room_id, start_at, end_at, exclude_booking_id=None):
        query = cls.query.filter(
            cls.room_id == room_id,
            cls.cancelled_at.is_(None),
            cls.start_at < end_at,
            cls.end_at > start_at,
        )
        if exclude_booking_id is not None:
            query = query.filter(cls.id != exclude_booking_id)
        return query.first()

    @classmethod
    def overlaps(cls, room_id, start_at, end_at, exclude_booking_id=None):
        return cls.find_conflict(room_id, start_at, end_at, exclude_booking_id) is not None

    def __repr__(self):
        return f"<Booking {self.title} room={self.room_id}>"
