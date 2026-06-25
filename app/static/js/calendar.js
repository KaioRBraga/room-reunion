document.addEventListener("DOMContentLoaded", function () {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const rooms = window.READYROOM_ROOMS || [];
    const unitFilter = document.getElementById("unitFilter");
    const roomFilter = document.getElementById("roomFilter");

    // Esconde do filtro de sala as salas que não pertencem à unidade
    // selecionada - mesmo padrão de unidade/andar já usado no mapa de salas.
    function applyUnitFilter() {
        if (!unitFilter) return;
        const unitId = unitFilter.value;
        let selectedHidden = false;
        Array.from(roomFilter.options).forEach((option) => {
            if (!option.value) return; // mantém sempre "Todas as salas"
            const matches = !unitId || option.dataset.unitId === unitId;
            option.hidden = !matches;
            if (!matches && option.selected) selectedHidden = true;
        });
        if (selectedHidden) roomFilter.value = "";
    }

    const modalEl = document.getElementById("bookingModal");
    const modal = new bootstrap.Modal(modalEl);
    const modalTitle = document.getElementById("bookingModalTitle");
    const modalError = document.getElementById("bookingModalError");
    const bookingMeta = document.getElementById("bookingMeta");
    const roomSelect = document.getElementById("bookingRoom");
    const titleInput = document.getElementById("bookingTitle");
    const startInput = document.getElementById("bookingStart");
    const endInput = document.getElementById("bookingEnd");
    const attendeesInput = document.getElementById("bookingAttendees");
    const attendeesHint = document.getElementById("bookingAttendeesHint");
    const virtualUrlInput = document.getElementById("bookingVirtualUrl");
    const attendeeSearchInput = document.getElementById("bookingAttendeeSearch");
    const attendeeResultsBox = document.getElementById("bookingAttendeeResults");
    const attendeeChipsBox = document.getElementById("bookingAttendeeChips");
    const descriptionInput = document.getElementById("bookingDescription");

    let selectedAttendees = [];
    let attendeeSearchTimer = null;
    let virtualUrlTouched = false;

    function stripDiacritics(text) {
        // NFD separa cada acento como um caractere combinante próprio (U+0300-U+036F);
        // filtrar por código evita depender de um literal unicode no código-fonte.
        let result = "";
        for (const ch of text.normalize("NFD")) {
            const code = ch.codePointAt(0);
            if (code < 0x0300 || code > 0x036f) {
                result += ch;
            }
        }
        return result;
    }

    function slugifyForJitsi(text) {
        return stripDiacritics(text || "")
            .replace(/[^a-zA-Z0-9\s]/g, "") // remove caracteres especiais
            .trim()
            .replace(/\s+/g, "_");
    }

    function updateVirtualUrlSuggestion() {
        if (virtualUrlTouched) return;
        const slug = slugifyForJitsi(titleInput.value);
        virtualUrlInput.value = slug ? "https://meet.jit.si/" + slug : "";
    }

    virtualUrlInput.addEventListener("input", function () {
        virtualUrlTouched = true;
    });
    titleInput.addEventListener("input", updateVirtualUrlSuggestion);

    function renderAttendeeChips() {
        attendeeChipsBox.innerHTML = "";
        selectedAttendees.forEach(function (person) {
            const chip = document.createElement("span");
            chip.className = "badge bg-secondary d-flex align-items-center gap-1";
            chip.textContent = person.display_name + " (" + person.email + ")";
            if (!attendeeSearchInput.disabled) {
                const removeBtn = document.createElement("button");
                removeBtn.type = "button";
                removeBtn.className = "btn-close btn-close-white";
                removeBtn.style.fontSize = "0.55em";
                removeBtn.setAttribute("aria-label", "Remover");
                removeBtn.addEventListener("click", function () {
                    selectedAttendees = selectedAttendees.filter((p) => p.email !== person.email);
                    renderAttendeeChips();
                });
                chip.appendChild(removeBtn);
            }
            attendeeChipsBox.appendChild(chip);
        });
    }

    function addAttendee(person) {
        if (selectedAttendees.some((p) => p.email === person.email)) return;
        selectedAttendees.push(person);
        renderAttendeeChips();
        attendeeSearchInput.value = "";
        attendeeResultsBox.innerHTML = "";
    }

    attendeeSearchInput.addEventListener("input", function () {
        clearTimeout(attendeeSearchTimer);
        const q = attendeeSearchInput.value.trim();
        if (q.length < 2) {
            attendeeResultsBox.innerHTML = "";
            return;
        }
        attendeeSearchTimer = setTimeout(function () {
            fetch("/bookings/api/people?q=" + encodeURIComponent(q))
                .then((res) => res.json())
                .then(function (people) {
                    attendeeResultsBox.innerHTML = "";
                    people.forEach(function (person) {
                        const item = document.createElement("button");
                        item.type = "button";
                        item.className = "list-group-item list-group-item-action";
                        item.textContent = person.display_name + " (" + person.email + ")";
                        item.addEventListener("click", () => addAttendee(person));
                        attendeeResultsBox.appendChild(item);
                    });
                });
        }, 300);
    });
    const saveBtn = document.getElementById("bookingSaveBtn");
    const cancelBtn = document.getElementById("bookingCancelBtn");

    let currentBookingId = null;

    function toLocalInputValue(date) {
        const pad = (n) => String(n).padStart(2, "0");
        return (
            date.getFullYear() +
            "-" + pad(date.getMonth() + 1) +
            "-" + pad(date.getDate()) +
            "T" + pad(date.getHours()) +
            ":" + pad(date.getMinutes())
        );
    }

    function showError(message) {
        modalError.textContent = message;
        modalError.classList.remove("d-none");
    }

    function updateAttendeesHint() {
        const room = rooms.find((r) => String(r.id) === String(roomSelect.value));
        if (room && room.min_attendees) {
            attendeesHint.textContent = "Esta sala exige no mínimo " + room.min_attendees + " participantes.";
            attendeesInput.min = room.min_attendees;
        } else {
            attendeesHint.textContent = "";
            attendeesInput.min = 1;
        }
    }

    function resetModal() {
        modalError.classList.add("d-none");
        bookingMeta.classList.add("d-none");
        cancelBtn.classList.add("d-none");
        saveBtn.classList.remove("d-none");
        roomSelect.disabled = false;
        titleInput.disabled = false;
        startInput.disabled = false;
        endInput.disabled = false;
        attendeesInput.disabled = false;
        virtualUrlInput.disabled = false;
        attendeeSearchInput.disabled = false;
        attendeeSearchInput.classList.remove("d-none");
        descriptionInput.disabled = false;
        currentBookingId = null;
        selectedAttendees = [];
        virtualUrlTouched = false;
        attendeeResultsBox.innerHTML = "";
        renderAttendeeChips();
    }

    function openCreateModal(start, end, roomId) {
        resetModal();
        modalTitle.textContent = "Nova reserva";
        roomSelect.value = roomId || (rooms[0] && rooms[0].id) || "";
        titleInput.value = "";
        startInput.value = toLocalInputValue(start);
        endInput.value = toLocalInputValue(end);
        attendeesInput.value = 1;
        virtualUrlInput.value = "";
        descriptionInput.value = "";
        updateAttendeesHint();
        modal.show();
    }

    function openViewModal(event) {
        resetModal();
        modalTitle.textContent = "Detalhes da reserva";
        currentBookingId = event.id;
        roomSelect.value = event.extendedProps.room_id;
        titleInput.value = event.extendedProps.raw_title;
        startInput.value = toLocalInputValue(event.start);
        endInput.value = toLocalInputValue(event.end);
        attendeesInput.value = event.extendedProps.attendees_count || 1;
        virtualUrlInput.value = event.extendedProps.virtual_room_url || "";
        descriptionInput.value = event.extendedProps.description || "";
        updateAttendeesHint();
        selectedAttendees = (event.extendedProps.attendee_emails || []).map((email) => ({
            email: email,
            display_name: email,
        }));

        roomSelect.disabled = true;
        titleInput.disabled = true;
        startInput.disabled = true;
        endInput.disabled = true;
        attendeesInput.disabled = true;
        virtualUrlInput.disabled = true;
        attendeeSearchInput.disabled = true;
        attendeeSearchInput.classList.add("d-none");
        renderAttendeeChips();
        descriptionInput.disabled = true;

        bookingMeta.textContent = "Organizador: " + event.extendedProps.organizer;
        bookingMeta.classList.remove("d-none");

        if (event.extendedProps.can_cancel) {
            cancelBtn.classList.remove("d-none");
        }
        saveBtn.classList.add("d-none");
        modal.show();
    }

    const calendarEl = document.getElementById("calendar");
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: "timeGridWeek",
        headerToolbar: {
            left: "prev,next today",
            center: "title",
            right: "multiMonthYear,dayGridMonth,timeGridWeek,timeGridDay",
        },
        locale: "pt-br",
        // O bundle do FullCalendar não traduz o texto dos botões a partir do
        // `locale` (só formatação de data/título) - força aqui pra não
        // ficar com "today/year/month/week/day" em inglês.
        buttonText: {
            today: "Hoje",
            year: "Ano",
            month: "Mês",
            week: "Semana",
            day: "Dia",
            list: "Lista",
        },
        height: "auto",
        slotMinTime: "07:00:00",
        slotMaxTime: "21:00:00",
        selectable: true,
        nowIndicator: true,
        events: function (info, successCallback, failureCallback) {
            const params = new URLSearchParams({
                start: info.startStr,
                end: info.endStr,
            });
            if (roomFilter.value) {
                params.set("room_id", roomFilter.value);
            }
            if (unitFilter && unitFilter.value) {
                params.set("unit_id", unitFilter.value);
            }
            fetch("/bookings/api/events?" + params.toString())
                .then((res) => res.json())
                .then(successCallback)
                .catch(failureCallback);
        },
        select: function (info) {
            openCreateModal(info.start, info.end, roomFilter.value);
        },
        eventClick: function (info) {
            openViewModal(info.event);
        },
    });
    calendar.render();

    roomFilter.addEventListener("change", function () {
        calendar.refetchEvents();
    });

    if (unitFilter) {
        applyUnitFilter();
        unitFilter.addEventListener("change", function () {
            applyUnitFilter();
            calendar.refetchEvents();
        });
    }

    roomSelect.addEventListener("change", updateAttendeesHint);

    saveBtn.addEventListener("click", function () {
        modalError.classList.add("d-none");
        const payload = {
            room_id: parseInt(roomSelect.value, 10),
            title: titleInput.value.trim(),
            start: startInput.value,
            end: endInput.value,
            attendees_count: parseInt(attendeesInput.value, 10) || 1,
            virtual_room_url: virtualUrlInput.value.trim(),
            attendee_emails: selectedAttendees.map((p) => p.email),
            description: descriptionInput.value.trim(),
        };

        fetch("/bookings/api/bookings", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(payload),
        })
            .then((res) => res.json().then((data) => ({ status: res.status, data })))
            .then(({ status, data }) => {
                if (status >= 400) {
                    showError(data.error || "Não foi possível salvar a reserva.");
                    return;
                }
                modal.hide();
                calendar.refetchEvents();
            })
            .catch(() => showError("Erro de comunicação com o servidor."));
    });

    cancelBtn.addEventListener("click", function () {
        if (!currentBookingId) return;
        fetch("/bookings/api/bookings/" + currentBookingId + "/cancel", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
        })
            .then((res) => {
                if (!res.ok) throw new Error();
                modal.hide();
                calendar.refetchEvents();
            })
            .catch(() => showError("Não foi possível cancelar a reserva."));
    });
});
