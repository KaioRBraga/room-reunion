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

    # Posição relativa (0.0-1.0) do pin sobre a imagem do andar (`Floor`).
    # None significa que a sala ainda não foi posicionada no mapa.
    pos_x = db.Column(db.Float, nullable=True)
    pos_y = db.Column(db.Float, nullable=True)

    # Andar ao qual a sala pertence. Nullable só por causa da migração leve
    # (ALTER TABLE em banco já existente, ver app/schema_migrations.py) - na
    # prática toda sala tem andar, preenchido automaticamente por
    # `ensure_default_floor()` num andar padrão se a coluna vier vazia.
    floor_id = db.Column(db.Integer, db.ForeignKey("floor.id"), nullable=True)

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


class DisplayLayoutSettings(db.Model):
    """Configuração global de aparência do painel/tablet (aba "Layout do painel",
    visível só para admin). Singleton (uma única linha, id=1) - o layout é o
    mesmo para todos os painéis, a personalização não é por sala.
    """

    __tablename__ = "display_layout_settings"

    DEFAULT_COLOR_AVAILABLE = "#1F9D55"
    DEFAULT_COLOR_STARTING_SOON = "#E0A100"
    DEFAULT_COLOR_IN_USE = "#DC3545"
    DEFAULT_AGENDA_POSITION = "below_status"
    DEFAULT_BUTTON_POSITION = "status_banner"

    AGENDA_POSITIONS = ("below_status", "above_status")
    BUTTON_POSITIONS = ("status_banner", "top_right")

    id = db.Column(db.Integer, primary_key=True)
    show_logo = db.Column(db.Boolean, default=True, nullable=False)
    show_tags = db.Column(db.Boolean, default=True, nullable=False)
    show_video_icon = db.Column(db.Boolean, default=True, nullable=False)
    show_schedule_hint = db.Column(db.Boolean, default=True, nullable=False)
    color_available = db.Column(db.String(7), default=DEFAULT_COLOR_AVAILABLE, nullable=False)
    color_starting_soon = db.Column(db.String(7), default=DEFAULT_COLOR_STARTING_SOON, nullable=False)
    color_in_use = db.Column(db.String(7), default=DEFAULT_COLOR_IN_USE, nullable=False)
    # Posição da agenda do dia em relação à faixa de status, e do botão de ação
    # principal (dentro da faixa de status ou isolado no canto superior
    # direito) - arranjos pré-definidos, editados via o botão "caneta" na aba
    # "Layout do painel" > "Tablet".
    agenda_position = db.Column(db.String(20), default=DEFAULT_AGENDA_POSITION, nullable=False)
    button_position = db.Column(db.String(20), default=DEFAULT_BUTTON_POSITION, nullable=False)
    # Logo específica do painel/tablet (diferente da logo do site em
    # SiteBrandingSettings) - None usa o asset padrão empacotado no app Flutter.
    logo_filename = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    updated_by = db.Column(db.String(120), nullable=True)

    @staticmethod
    def get_settings():
        settings = db.session.get(DisplayLayoutSettings, 1)
        if settings is None:
            settings = DisplayLayoutSettings(id=1)
            db.session.add(settings)
            db.session.commit()
        return settings

    def reset_to_defaults(self):
        self.show_logo = True
        self.show_tags = True
        self.show_video_icon = True
        self.show_schedule_hint = True
        self.color_available = self.DEFAULT_COLOR_AVAILABLE
        self.color_starting_soon = self.DEFAULT_COLOR_STARTING_SOON
        self.color_in_use = self.DEFAULT_COLOR_IN_USE
        self.agenda_position = self.DEFAULT_AGENDA_POSITION
        self.button_position = self.DEFAULT_BUTTON_POSITION
        self.logo_filename = None

    def to_payload(self):
        return {
            "show_logo": self.show_logo,
            "show_tags": self.show_tags,
            "show_video_icon": self.show_video_icon,
            "show_schedule_hint": self.show_schedule_hint,
            "agenda_position": self.agenda_position,
            "button_position": self.button_position,
            "colors": {
                "available": self.color_available,
                "starting_soon": self.color_starting_soon,
                "in_use": self.color_in_use,
            },
        }

    def __repr__(self):
        return "<DisplayLayoutSettings>"


class SiteBrandingSettings(db.Model):
    """Identidade visual do site (aba "Layout do painel" > "Site", admin-only):
    logo, ícone (marca pequena/favicon), cor primária e secundária. Singleton
    (uma única linha, id=1), aplicada a todas as páginas via context
    processor (`app/__init__.py`).
    """

    __tablename__ = "site_branding_settings"

    DEFAULT_PRIMARY_COLOR = "#007BBB"
    DEFAULT_SECONDARY_COLOR = "#0B2545"

    id = db.Column(db.Integer, primary_key=True)
    logo_filename = db.Column(db.String(255), nullable=True)
    icon_filename = db.Column(db.String(255), nullable=True)
    primary_color = db.Column(db.String(7), default=DEFAULT_PRIMARY_COLOR, nullable=False)
    secondary_color = db.Column(db.String(7), default=DEFAULT_SECONDARY_COLOR, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    updated_by = db.Column(db.String(120), nullable=True)

    @staticmethod
    def get_settings():
        settings = db.session.get(SiteBrandingSettings, 1)
        if settings is None:
            settings = SiteBrandingSettings(id=1)
            db.session.add(settings)
            db.session.commit()
        return settings

    def reset_to_defaults(self):
        self.logo_filename = None
        self.icon_filename = None
        self.primary_color = self.DEFAULT_PRIMARY_COLOR
        self.secondary_color = self.DEFAULT_SECONDARY_COLOR

    @staticmethod
    def _hex_to_rgb(hex_color):
        h = hex_color.lstrip("#")
        return ", ".join(str(int(h[i : i + 2], 16)) for i in (0, 2, 4))

    @property
    def primary_rgb(self):
        return self._hex_to_rgb(self.primary_color)

    @property
    def secondary_rgb(self):
        return self._hex_to_rgb(self.secondary_color)

    def __repr__(self):
        return "<SiteBrandingSettings>"


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


class Unit(db.Model):
    """Prédio/site - agrupa um ou mais `Floor`."""

    __tablename__ = "unit"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    floors = db.relationship("Floor", backref="unit", lazy="dynamic")

    def __repr__(self):
        return f"<Unit {self.name}>"


class Floor(db.Model):
    """Andar dentro de uma `Unit`, com sua própria planta baixa.

    Substitui o antigo singleton `FloorMap` (uma planta global pra todas as
    salas) - os campos de arquivo da planta (`filename` etc.) que antes
    viviam em `FloorMap` agora ficam aqui, um conjunto por andar.
    """

    __tablename__ = "floor"
    __table_args__ = (db.UniqueConstraint("unit_id", "name", name="uq_floor_unit_name"),)

    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey("unit.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # Planta baixa do andar - None enquanto nenhum admin fez upload ainda.
    filename = db.Column(db.String(255), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    uploaded_by = db.Column(db.String(120), nullable=True)
    uploaded_at = db.Column(db.DateTime, nullable=True)

    rooms = db.relationship("Room", backref="floor", lazy="dynamic")

    def __repr__(self):
        return f"<Floor {self.name} unit={self.unit_id}>"


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
