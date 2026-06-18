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
    const equipmentInput = document.getElementById("roomPinEquipment");
    const availabilityInput = document.getElementById("roomPinAvailability");
    const saveBtn = document.getElementById("roomPinSaveBtn");
    const unpinBtn = document.getElementById("roomPinUnpinBtn");
    const bookBtn = document.getElementById("roomPinBookBtn");
    const fields = [nameInput, capacityInput, equipmentInput, availabilityInput];

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

    function attachPinHandlers(el) {
        el.addEventListener("click", () => openViewModal(el.dataset.roomId));
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
                equipmentInput.value = "";
                availabilityInput.value = "";
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
                equipmentInput.value = room.equipment_notes;
                availabilityInput.value = room.availability_notes;

                statusBox.textContent = room.is_occupied_now ? "Ocupada agora" : "Livre agora";
                statusBox.className = "badge mb-3 " + (room.is_occupied_now ? "bg-danger" : "bg-success");
                statusBox.classList.remove("d-none");
                updatePinStatus(room.id, room.is_occupied_now);

                bookBtn.dataset.roomId = room.id;
                bookBtn.dataset.roomName = room.name;
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
            equipment_notes: equipmentInput.value.trim(),
            availability_notes: availabilityInput.value.trim(),
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

    unpinBtn.addEventListener("click", function () {
        if (!currentRoomId) return;
        fetch("/rooms/pins/" + currentRoomId + "/unpin", {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
        }).then(() => {
            const el = mapWrap.querySelector('.room-pin[data-room-id="' + currentRoomId + '"]');
            if (el) el.remove();
            modal.hide();
        });
    });

    // --- Mini calendário de reserva, aberto a partir do pin ---

    const reserveModalEl = document.getElementById("reserveModal");
    const reserveModal = new bootstrap.Modal(reserveModalEl);
    const reserveModalTitle = document.getElementById("reserveModalTitle");
    const reserveError = document.getElementById("reserveError");
    const reserveCalendarEl = document.getElementById("reserveCalendar");
    const reserveFormWrap = document.getElementById("reserveFormWrap");
    const reserveRangeLabel = document.getElementById("reserveRangeLabel");
    const reserveTitleInput = document.getElementById("reserveTitle");
    const reserveDescriptionInput = document.getElementById("reserveDescription");
    const reserveConfirmBtn = document.getElementById("reserveConfirmBtn");
    const reserveCancelSelectionBtn = document.getElementById("reserveCancelSelectionBtn");

    let reserveCalendar = null;
    let reserveRoomId = null;
    let reserveSelection = null;

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

    function openReserveModal(roomId, roomName) {
        reserveRoomId = roomId;
        reserveSelection = null;
        reserveModalTitle.textContent = "Reservar - " + roomName;
        reserveError.classList.add("d-none");
        reserveFormWrap.classList.add("d-none");

        if (reserveCalendar) {
            reserveCalendar.destroy();
        }
        reserveCalendar = new FullCalendar.Calendar(reserveCalendarEl, {
            initialView: "timeGridWeek",
            height: 450,
            locale: "pt-br",
            headerToolbar: { left: "prev,next today", center: "title", right: "timeGridWeek,timeGridDay" },
            slotMinTime: "07:00:00",
            slotMaxTime: "21:00:00",
            selectable: true,
            events: "/bookings/api/events?room_id=" + roomId,
            select: function (info) {
                reserveSelection = { start: info.start, end: info.end };
                reserveRangeLabel.textContent = formatRange(info.start, info.end);
                reserveTitleInput.value = "";
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
    }

    bookBtn.addEventListener("click", function () {
        const roomId = bookBtn.dataset.roomId;
        const roomName = bookBtn.dataset.roomName;
        if (!roomId) return;
        modal.hide();
        openReserveModal(roomId, roomName);
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