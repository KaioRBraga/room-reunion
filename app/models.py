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

    # Mínimo de participantes para reservar a sala (3-5, definido pelo admin
    # no cadastro). None = sem mínimo.
    min_attendees = db.Column(db.Integer, nullable=True)

    # Janela de horário comercial em que a sala pode ser reservada.
    # None em qualquer um dos dois = sem restrição de horário.
    business_hours_start = db.Column(db.Time, nullable=True)
    business_hours_end = db.Column(db.Time, nullable=True)

    bookings = db.relationship(
        "Booking", backref="room", lazy="dynamic", cascade="all, delete-orphan"
    )
    booking_groups = db.relationship(
        "RoomBookingGroup", backref="room", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def is_on_map(self):
        return self.pos_x is not None and self.pos_y is not None

    @property
    def allowed_group_cns(self):
        return [g.group_cn for g in self.booking_groups]

    def is_bookable_by(self, group_cns, is_admin=False):
        """Sala sem grupo associado fica aberta a qualquer usuário logado."""
        if is_admin:
            return True
        allowed = self.allowed_group_cns
        if not allowed:
            return True
        return bool(set(group_cns or []) & set(allowed))

    def is_within_business_hours(self, start_at, end_at):
        if self.business_hours_start is None or self.business_hours_end is None:
            return True
        return (
            start_at.time() >= self.business_hours_start
            and end_at.time() <= self.business_hours_end
        )

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


class User(db.Model):
    """Cadastro local, alimentado a cada login bem-sucedido no AD.

    Guarda dados que não existem na sessão (e-mail, PIN do tablet) e serve de
    base para busca de pessoas ao convidar participantes de uma reunião.
    """

    __tablename__ = "user"

    username = db.Column(db.String(120), primary_key=True)
    display_name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    # Criptografado (não hash) para poder ser exibido de volta no perfil após
    # confirmação de senha - ver app/auth/pin_crypto.py.
    pin_encrypted = db.Column(db.String(255), nullable=True)
    avatar_filename = db.Column(db.String(255), nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"


class BookingAttendee(db.Model):
    """Pessoa convidada para a reunião (e-mail e, quando encontrado, username).

    Alimenta a notificação por e-mail (ainda não implementada - depende do
    SMTP corporativo) e, futuramente, o redirecionamento para a sala virtual.
    """

    __tablename__ = "booking_attendee"
    __table_args__ = (
        db.UniqueConstraint("booking_id", "email", name="uq_booking_attendee_email"),
    )

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    username = db.Column(db.String(120), nullable=True)

    def __repr__(self):
        return f"<BookingAttendee booking={self.booking_id} email={self.email}>"


class RoomBookingGroup(db.Model):
    """Grupo do AD (cn) autorizado a reservar uma sala específica.

    Camada separada do admin de salas (`GRUPOS_ADMIN_SALAS`): controla quem
    pode *agendar* a sala, não quem pode administrá-la.
    """

    __tablename__ = "room_booking_group"
    __table_args__ = (
        db.UniqueConstraint("room_id", "group_cn", name="uq_room_booking_group"),
    )

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("room.id"), nullable=False)
    group_cn = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"<RoomBookingGroup room={self.room_id} group={self.group_cn}>"


class ReportViewerGroup(db.Model):
    """Grupo do AD (cn) autorizado a ver o dashboard de relatórios.

    Permissão global (não por sala, diferente de `RoomBookingGroup`): sem
    nenhum grupo cadastrado, só administradores (`GRUPOS_ADMIN_SALAS`) veem
    o relatório - é dado agregado sobre reservas de todo mundo, então aqui o
    padrão é restritivo, ao contrário do agendamento de sala.
    """

    __tablename__ = "report_viewer_group"

    id = db.Column(db.Integer, primary_key=True)
    group_cn = db.Column(db.String(200), unique=True, nullable=False)

    def __repr__(self):
        return f"<ReportViewerGroup group={self.group_cn}>"

    @staticmethod
    def allowed_cns():
        return [g.group_cn for g in ReportViewerGroup.query.all()]

    @staticmethod
    def can_view(group_cns, is_admin=False):
        if is_admin:
            return True
        allowed = ReportViewerGroup.allowed_cns()
        if not allowed:
            return False
        return bool(set(group_cns or []) & set(allowed))


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
    attendees_count = db.Column(db.Integer, nullable=False, default=1, server_default="1")

    # URL da sala virtual (Teams/Meet/Zoom etc), preenchida pelo organizador
    # para incluir pessoas remotas na reunião.
    virtual_room_url = db.Column(db.String(500), nullable=True)

    attendees = db.relationship(
        "BookingAttendee", backref="booking", lazy="dynamic", cascade="all, delete-orphan"
    )

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
