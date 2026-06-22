document.addEventListener("DOMContentLoaded", function () {
    const mapWrap = document.getElementById("mapWrap");
    if (!mapWrap) return;

    const isAdmin = document.body.dataset.isAdmin === "1";
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const newRoomPin = document.getElementById("newRoomPin");

    const modalEl = document.getElementById("roomPinModal");
    const modal = new bootstrap.Modal(modalEl);
    const modalTitle = document.getElementById("roomPinModalTitle");
    const errorBox = document.getElementById("roomPinError");
    const statusBox = document.getElementById("roomPinStatus");
    const nameInput = document.getElementById("roomPinName");
    const capacityInput = document.getElementById("roomPinCapacity");
    const equipmentCheckboxes = Array.from(document.querySelectorAll(".room-pin-equipment-checkbox"));
    const equipmentOtherInput = document.getElementById("roomPinEquipmentOther");
    const availabilityInput = document.getElementById("roomPinAvailability");
    const businessStartInput = document.getElementById("roomPinBusinessStart");
    const businessEndInput = document.getElementById("roomPinBusinessEnd");
    const saveBtn = document.getElementById("roomPinSaveBtn");
    const unpinBtn = document.getElementById("roomPinUnpinBtn");
    const bookBtn = document.getElementById("roomPinBookBtn");
    const equipmentOptions = window.READYROOM_EQUIPMENT_OPTIONS || [];
    const fields = [
        nameInput,
        capacityInput,
        availabilityInput,
        businessStartInput,
        businessEndInput,
        equipmentOtherInput,
        ...equipmentCheckboxes,
    ];

    function getEquipmentNotes() {
        const checked = equipmentCheckboxes.filter((el) => el.checked).map((el) => el.value);
        const other = equipmentOtherInput.value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
        return checked.concat(other).join(", ");
    }

    function setEquipmentForm(equipmentNotes) {
        // Salas cadastradas antes do checklist podem ter o texto separado por
        // quebra de linha em vez de vírgula (era um textarea) - aceita os dois.
        const items = (equipmentNotes || "").split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
        equipmentCheckboxes.forEach((el) => {
            el.checked = items.includes(el.value);
        });
        equipmentOtherInput.value = items.filter((i) => !equipmentOptions.includes(i)).join(", ");
    }

    let currentRoomId = null;
    let pendingPos = null;

    function showError(message) {
        errorBox.textContent = message;
        errorBox.classList.remove("d-none");
    }

    function showSuccess(message) {
        // Você pode implementar um toast ou alerta de sucesso aqui
        alert(message); // Temporário - substitua por um toast bonito
    }

    function resetModal() {
        errorBox.classList.add("d-none");
        statusBox.classList.add("d-none");
        unpinBtn.classList.add("d-none");
        bookBtn.classList.add("d-none");
        saveBtn.classList.remove("d-none");
        fields.forEach((el) => (el.disabled = false));
        currentRoomId = null;
        pendingPos = null;
    }

    function relativePosFromEvent(evt) {
        const rect = mapWrap.getBoundingClientRect();
        const x = (evt.clientX - rect.left) / rect.width;
        const y = (evt.clientY - rect.top) / rect.height;
        return { x: Math.min(Math.max(x, 0), 1), y: Math.min(Math.max(y, 0), 1) };
    }

    function placePin(el, x, y) {
        el.style.left = x * 100 + "%";
        el.style.top = y * 100 + "%";
    }

    // Usuário comum não precisa ver/editar as configurações da sala - vai
    // direto para o formulário de reserva. Só admin passa pela tela de detalhes
    // (que também serve para editar nome/capacidade/equipamentos/horário).
    function openReserveModalForRoom(roomId) {
        fetch("/rooms/pins/" + roomId)
            .then((res) => res.json())
            .then((room) => {
                updatePinStatus(room.id, room.is_occupied_now);
                openReserveModal(room.id, room.name, room.min_attendees);
            });
    }

    function attachPinHandlers(el) {
        el.addEventListener("click", () => {
            if (isAdmin) {
                openViewModal(el.dataset.roomId);
            } else {
                openReserveModalForRoom(el.dataset.roomId);
            }
        });
        if (isAdmin) {
            el.addEventListener("dragstart", (evt) => {
                evt.dataTransfer.setData("text/plain", "move:" + el.dataset.roomId);
            });
        }
    }

    function createPinElement(room) {
        const el = document.createElement("div");
        el.className = "room-pin";
        el.dataset.roomId = room.id;
        el.draggable = isAdmin;
        placePin(el, room.pos_x, room.pos_y);
        const label = document.createElement("span");
        label.className = "room-pin-label";
        label.textContent = room.name;
        el.appendChild(label);
        
        // Adiciona classe de status ao criar
        el.classList.add(room.is_occupied_now ? "occupied" : "available");
        
        attachPinHandlers(el);
        return el;
    }

    mapWrap.querySelectorAll(".room-pin[data-room-id]").forEach(attachPinHandlers);

    if (isAdmin && newRoomPin) {
        newRoomPin.addEventListener("dragstart", (evt) => {
            evt.dataTransfer.setData("text/plain", "create");
        });

        mapWrap.addEventListener("dragover", (evt) => evt.preventDefault());

        mapWrap.addEventListener("drop", (evt) => {
            evt.preventDefault();
            const payload = evt.dataTransfer.getData("text/plain");
            if (!payload) return;
            const pos = relativePosFromEvent(evt);

            if (payload === "create") {
                resetModal();
                pendingPos = pos;
                modalTitle.textContent = "Nova sala";
                nameInput.value = "";
                capacityInput.value = "";
                setEquipmentForm("");
                availabilityInput.value = "";
                businessStartInput.value = "";
                businessEndInput.value = "";
                modal.show();
            } else if (payload.startsWith("move:")) {
                moveRoom(payload.slice(5), pos);
            }
        });
    }

    function moveRoom(roomId, pos) {
        fetch("/rooms/pins/" + roomId, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
            body: JSON.stringify({ pos_x: pos.x, pos_y: pos.y }),
        })
            .then((res) => res.json())
            .then((data) => {
                const el = mapWrap.querySelector('.room-pin[data-room-id="' + roomId + '"]');
                if (el) placePin(el, data.pos_x, data.pos_y);
            });
    }

    function openViewModal(roomId) {
        fetch("/rooms/pins/" + roomId)
            .then((res) => res.json())
            .then((room) => {
                resetModal();
                currentRoomId = room.id;
                modalTitle.textContent = room.name;
                nameInput.value = room.name;
                capacityInput.value = room.capacity;
                setEquipmentForm(room.equipment_notes);
                availabilityInput.value = room.availability_notes;
                businessStartInput.value = room.business_hours_start || "";
                businessEndInput.value = room.business_hours_end || "";

                statusBox.textContent = room.is_occupied_now ? "Ocupada agora" : "Livre agora";
                statusBox.className = "badge mb-3 " + (room.is_occupied_now ? "bg-danger" : "bg-success");
                statusBox.classList.remove("d-none");
                updatePinStatus(room.id, room.is_occupied_now);

                bookBtn.dataset.roomId = room.id;
                bookBtn.dataset.roomName = room.name;
                bookBtn.dataset.minAttendees = room.min_attendees || "";
                bookBtn.classList.remove("d-none");

                if (room.can_edit) {
                    unpinBtn.classList.remove("d-none");
                } else {
                    fields.forEach((el) => (el.disabled = true));
                    saveBtn.classList.add("d-none");
                }
                modal.show();
            });
    }

    function updatePinStatus(roomId, isOccupied) {
        const pinElement = mapWrap.querySelector('.room-pin[data-room-id="' + roomId + '"]');
        if (pinElement) {
            pinElement.classList.remove("occupied", "available");
            pinElement.classList.add(isOccupied ? "occupied" : "available");
        }
    }

    // Busca o status real (calculado no servidor) em vez de assumir que toda
    // reserva criada/cancelada afeta o "agora" - a reserva pode ser para outro horário.
    function refreshPinStatus(roomId) {
        fetch("/rooms/pins/" + roomId)
            .then((res) => res.json())
            .then((room) => updatePinStatus(roomId, room.is_occupied_now));
    }

    saveBtn.addEventListener("click", function () {
        errorBox.classList.add("d-none");
        const payload = {
            name: nameInput.value.trim(),
            capacity: parseInt(capacityInput.value, 10),
            equipment_notes: getEquipmentNotes(),
            availability_notes: availabilityInput.value.trim(),
            business_hours_start: businessStartInput.value,
            business_hours_end: businessEndInput.value,
        };

        let url = "/rooms/pins";
        if (currentRoomId) {
            url = "/rooms/pins/" + currentRoomId;
        } else {
            if (!pendingPos) return;
            payload.pos_x = pendingPos.x;
            payload.pos_y = pendingPos.y;
        }

        fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
            body: JSON.stringify(payload),
        })
            .then((res) => res.json().then((data) => ({ status: res.status, data })))
            .then(({ status, data }) => {
                if (status >= 400) {
                    showError(data.error || "Não foi possível salvar.");
                    return;
                }
                if (!currentRoomId) {
                    mapWrap.appendChild(createPinElement(data));
                } else {
                    const el = mapWrap.querySelector('.room-pin[data-room-id="' + data.id + '"]');
                    if (el) el.querySelector(".room-pin-label").textContent = data.name;
                }
                modal.hide();
            })
            .catch(() => showError("Erro de comunicação com o servidor."));
    });

    function unpinRoom(roomId) {
        return fetch("/rooms/pins/" + roomId + "/unpin", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
        }).then(() => {
            const el = mapWrap.querySelector('.room-pin[data-room-id="' + roomId + '"]');
            if (el) el.remove();
        });
    }

    // Arrastar pra lixeira desativa a sala de vez (diferente do botão "Remover
    // do mapa", que só tira a posição e mantém a sala ativa/reservável).
    function discardRoom(roomId) {
        return fetch("/rooms/pins/" + roomId + "/discard", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
        }).then(() => {
            const el = mapWrap.querySelector('.room-pin[data-room-id="' + roomId + '"]');
            if (el) el.remove();
        });
    }

    unpinBtn.addEventListener("click", function () {
        if (!currentRoomId) return;
        unpinRoom(currentRoomId).then(() => modal.hide());
    });

    // --- Lixeira fixa: arrastar um pin até aqui desativa a sala ---

    const trashZone = document.getElementById("roomTrashZone");
    if (isAdmin && trashZone) {
        trashZone.addEventListener("dragover", (evt) => {
            evt.preventDefault();
            trashZone.style.transform = "scale(1.15)";
        });
        trashZone.addEventListener("dragleave", () => {
            trashZone.style.transform = "scale(1)";
        });
        trashZone.addEventListener("drop", (evt) => {
            evt.preventDefault();
            trashZone.style.transform = "scale(1)";
            const payload = evt.dataTransfer.getData("text/plain");
            if (!payload || !payload.startsWith("move:")) return;
            const roomId = payload.slice(5);
            if (!confirm("Desativar esta sala? Ela vai sumir do mapa e da lista de salas ativas.")) return;
            discardRoom(roomId);
        });
    }

    // --- Mini calendário de reserva, aberto a partir do pin ---

    const reserveModalEl = document.getElementById("reserveModal");
    const reserveModal = new bootstrap.Modal(reserveModalEl);
    const reserveModalTitle = document.getElementById("reserveModalTitle");
    const reserveError = document.getElementById("reserveError");
    const reserveCalendarEl = document.getElementById("reserveCalendar");
    const reserveFormWrap = document.getElementById("reserveFormWrap");
    const reserveRangeLabel = document.getElementById("reserveRangeLabel");
    const reserveTitleInput = document.getElementById("reserveTitle");
    const reserveAttendeesInput = document.getElementById("reserveAttendees");
    const reserveAttendeesHint = document.getElementById("reserveAttendeesHint");
    const reserveVirtualUrlInput = document.getElementById("reserveVirtualUrl");
    const reserveAttendeeSearchInput = document.getElementById("reserveAttendeeSearch");
    const reserveAttendeeResultsBox = document.getElementById("reserveAttendeeResults");
    const reserveAttendeeChipsBox = document.getElementById("reserveAttendeeChips");
    const reserveDescriptionInput = document.getElementById("reserveDescription");
    const reserveConfirmBtn = document.getElementById("reserveConfirmBtn");
    const reserveCancelSelectionBtn = document.getElementById("reserveCancelSelectionBtn");
    const reserveDateInput = document.getElementById("reserveDateInput");
    const reserveStartSelect = document.getElementById("reserveStartSelect");
    const reserveEndSelect = document.getElementById("reserveEndSelect");
    const reserveApplyTimeBtn = document.getElementById("reserveApplyTimeBtn");

    let reserveCalendar = null;
    let reserveRoomId = null;
    let reserveSelection = null;
    let reserveMinAttendees = null;
    let reserveSelectedAttendees = [];
    let reserveAttendeeSearchTimer = null;
    let reserveVirtualUrlTouched = false;

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

    function updateReserveVirtualUrlSuggestion() {
        if (reserveVirtualUrlTouched) return;
        const slug = slugifyForJitsi(reserveTitleInput.value);
        reserveVirtualUrlInput.value = slug ? "https://meet.jit.si/" + slug : "";
    }

    reserveVirtualUrlInput.addEventListener("input", function () {
        reserveVirtualUrlTouched = true;
    });
    reserveTitleInput.addEventListener("input", updateReserveVirtualUrlSuggestion);

    function renderReserveAttendeeChips() {
        reserveAttendeeChipsBox.innerHTML = "";
        reserveSelectedAttendees.forEach(function (person) {
            const chip = document.createElement("span");
            chip.className = "badge bg-secondary d-flex align-items-center gap-1";
            chip.textContent = person.display_name + " (" + person.email + ")";
            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "btn-close btn-close-white";
            removeBtn.style.fontSize = "0.55em";
            removeBtn.setAttribute("aria-label", "Remover");
            removeBtn.addEventListener("click", function () {
                reserveSelectedAttendees = reserveSelectedAttendees.filter((p) => p.email !== person.email);
                renderReserveAttendeeChips();
            });
            chip.appendChild(removeBtn);
            reserveAttendeeChipsBox.appendChild(chip);
        });
    }

    function addReserveAttendee(person) {
        if (reserveSelectedAttendees.some((p) => p.email === person.email)) return;
        reserveSelectedAttendees.push(person);
        renderReserveAttendeeChips();
        reserveAttendeeSearchInput.value = "";
        reserveAttendeeResultsBox.innerHTML = "";
    }

    reserveAttendeeSearchInput.addEventListener("input", function () {
        clearTimeout(reserveAttendeeSearchTimer);
        const q = reserveAttendeeSearchInput.value.trim();
        if (q.length < 2) {
            reserveAttendeeResultsBox.innerHTML = "";
            return;
        }
        reserveAttendeeSearchTimer = setTimeout(function () {
            fetch("/bookings/api/people?q=" + encodeURIComponent(q))
                .then((res) => res.json())
                .then(function (people) {
                    reserveAttendeeResultsBox.innerHTML = "";
                    people.forEach(function (person) {
                        const item = document.createElement("button");
                        item.type = "button";
                        item.className = "list-group-item list-group-item-action";
                        item.textContent = person.display_name + " (" + person.email + ")";
                        item.addEventListener("click", () => addReserveAttendee(person));
                        reserveAttendeeResultsBox.appendChild(item);
                    });
                });
        }, 300);
    });

    function toLocalIso(date) {
        const pad = (n) => String(n).padStart(2, "0");
        return (
            date.getFullYear() +
            "-" + pad(date.getMonth() + 1) +
            "-" + pad(date.getDate()) +
            "T" + pad(date.getHours()) +
            ":" + pad(date.getMinutes())
        );
    }

    function formatRange(start, end) {
        const dateOpts = { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" };
        const timeOpts = { hour: "2-digit", minute: "2-digit" };
        return start.toLocaleString("pt-BR", dateOpts) + " - " + end.toLocaleString("pt-BR", timeOpts);
    }

    function toDateInputValue(date) {
        const pad = (n) => String(n).padStart(2, "0");
        return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
    }

    function toHHMM(date) {
        const pad = (n) => String(n).padStart(2, "0");
        return pad(date.getHours()) + ":" + pad(date.getMinutes());
    }

    function nextHalfHour(date) {
        const result = new Date(date);
        result.setSeconds(0, 0);
        const remainder = result.getMinutes() % 30;
        result.setMinutes(result.getMinutes() + (remainder === 0 ? 30 : 30 - remainder));
        return result;
    }

    // Mantém o horário padrão dentro da janela visível da agenda
    // (slotMinTime/slotMaxTime) mesmo se "agora" for de madrugada/noite.
    function clampToVisibleRange(date) {
        const result = new Date(date);
        if (result.getHours() < 7) {
            result.setHours(7, 0, 0, 0);
        } else if (result.getHours() >= 21) {
            result.setHours(20, 30, 0, 0);
        }
        return result;
    }

    // Aplica a data/horário escolhidos nos dropdowns como se o usuário tivesse
    // arrastado a seleção direto na agenda (reaproveita o callback `select`).
    function applyDropdownSelection() {
        if (!reserveCalendar || !reserveDateInput.value) return;
        const start = new Date(reserveDateInput.value + "T" + reserveStartSelect.value + ":00");
        const end = new Date(reserveDateInput.value + "T" + reserveEndSelect.value + ":00");
        if (end <= start) {
            reserveError.textContent = "O horário de término deve ser depois do início.";
            reserveError.classList.remove("d-none");
            return;
        }
        reserveCalendar.gotoDate(start);
        reserveCalendar.select(start, end);
    }

    [reserveDateInput, reserveStartSelect, reserveEndSelect].forEach((el) =>
        el.addEventListener("change", applyDropdownSelection)
    );
    reserveApplyTimeBtn.addEventListener("click", applyDropdownSelection);

    function openReserveModal(roomId, roomName, minAttendees) {
        reserveRoomId = roomId;
        reserveSelection = null;
        reserveMinAttendees = minAttendees ? parseInt(minAttendees, 10) : null;
        reserveModalTitle.textContent = "Reservar - " + roomName;
        reserveError.classList.add("d-none");
        reserveFormWrap.classList.add("d-none");
        reserveSelectedAttendees = [];
        reserveVirtualUrlTouched = false;
        reserveAttendeeResultsBox.innerHTML = "";
        renderReserveAttendeeChips();
        if (reserveMinAttendees) {
            reserveAttendeesHint.textContent = "Esta sala exige no mínimo " + reserveMinAttendees + " participantes.";
            reserveAttendeesInput.min = reserveMinAttendees;
        } else {
            reserveAttendeesHint.textContent = "";
            reserveAttendeesInput.min = 1;
        }

        const defaultStart = clampToVisibleRange(nextHalfHour(new Date()));
        const defaultEnd = new Date(defaultStart.getTime() + 30 * 60000);
        reserveDateInput.value = toDateInputValue(defaultStart);
        reserveStartSelect.value = toHHMM(defaultStart);
        reserveEndSelect.value = toHHMM(defaultEnd);

        if (reserveCalendar) {
            reserveCalendar.destroy();
        }
        reserveCalendar = new FullCalendar.Calendar(reserveCalendarEl, {
            initialView: "timeGridDay",
            height: 450,
            locale: "pt-br",
            headerToolbar: { left: "prev,next today", center: "title", right: "timeGridDay,timeGridWeek" },
            slotMinTime: "07:00:00",
            slotMaxTime: "21:00:00",
            selectable: true,
            events: "/bookings/api/events?room_id=" + roomId,
            select: function (info) {
                reserveSelection = { start: info.start, end: info.end };
                reserveRangeLabel.textContent = formatRange(info.start, info.end);
                reserveTitleInput.value = "";
                reserveAttendeesInput.value = reserveMinAttendees || 1;
                reserveVirtualUrlInput.value = "";
                reserveDescriptionInput.value = "";
                reserveError.classList.add("d-none");
                reserveFormWrap.classList.remove("d-none");
            },
            eventClick: function (info) {
                if (!info.event.extendedProps.can_cancel) return;
                if (!confirm("Cancelar a reserva '" + info.event.title + "'?")) return;
                fetch("/bookings/api/bookings/" + info.event.id + "/cancel", {
                    method: "POST",
                    headers: { "X-CSRFToken": csrfToken },
                }).then(() => {
                    reserveCalendar.refetchEvents();
                    refreshPinStatus(reserveRoomId);
                });
            },
        });
        reserveCalendar.render();
        reserveModal.show();
        applyDropdownSelection();
    }

    bookBtn.addEventListener("click", function () {
        const roomId = bookBtn.dataset.roomId;
        const roomName = bookBtn.dataset.roomName;
        if (!roomId) return;
        modal.hide();
        openReserveModal(roomId, roomName, bookBtn.dataset.minAttendees);
    });

    reserveCancelSelectionBtn.addEventListener("click", function () {
        reserveFormWrap.classList.add("d-none");
        reserveSelection = null;
        if (reserveCalendar) reserveCalendar.unselect();
    });

    reserveConfirmBtn.addEventListener("click", function () {
        reserveError.classList.add("d-none");
        if (!reserveSelection) return;

        const title = reserveTitleInput.value.trim();
        if (!title) {
            reserveError.textContent = "Informe um título para a reserva.";
            reserveError.classList.remove("d-none");
            return;
        }

        const payload = {
            room_id: parseInt(reserveRoomId, 10),
            title: title,
            start: toLocalIso(reserveSelection.start),
            end: toLocalIso(reserveSelection.end),
            attendees_count: parseInt(reserveAttendeesInput.value, 10) || 1,
            virtual_room_url: reserveVirtualUrlInput.value.trim(),
            attendee_emails: reserveSelectedAttendees.map((p) => p.email),
            description: reserveDescriptionInput.value.trim(),
        };

        fetch("/bookings/api/bookings", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
            body: JSON.stringify(payload),
        })
            .then((res) => res.json().then((data) => ({ status: res.status, data })))
            .then(({ status, data }) => {
                if (status >= 400) {
                    reserveError.textContent = data.error || "Não foi possível reservar.";
                    reserveError.classList.remove("d-none");
                    return;
                }
                refreshPinStatus(reserveRoomId);

                reserveFormWrap.classList.add("d-none");
                reserveSelection = null;
                reserveSelectedAttendees = [];
                renderReserveAttendeeChips();
                reserveCalendar.unselect();
                reserveCalendar.refetchEvents();

                showSuccess("Reserva criada com sucesso!");
            })
            .catch(() => {
                reserveError.textContent = "Erro de comunicação com o servidor.";
                reserveError.classList.remove("d-none");
            });
    });
});