document.addEventListener("DOMContentLoaded", function () {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const rooms = window.READYROOM_ROOMS || [];
    const roomFilter = document.getElementById("roomFilter");

    const modalEl = document.getElementById("bookingModal");
    const modal = new bootstrap.Modal(modalEl);
    const modalTitle = document.getElementById("bookingModalTitle");
    const modalError = document.getElementById("bookingModalError");
    const bookingMeta = document.getElementById("bookingMeta");
    const roomSelect = document.getElementById("bookingRoom");
    const titleInput = document.getElementById("bookingTitle");
    const startInput = document.getElementById("bookingStart");
    const endInput = document.getElementById("bookingEnd");
    const descriptionInput = document.getElementById("bookingDescription");
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

    function resetModal() {
        modalError.classList.add("d-none");
        bookingMeta.classList.add("d-none");
        cancelBtn.classList.add("d-none");
        saveBtn.classList.remove("d-none");
        roomSelect.disabled = false;
        titleInput.disabled = false;
        startInput.disabled = false;
        endInput.disabled = false;
        descriptionInput.disabled = false;
        currentBookingId = null;
    }

    function openCreateModal(start, end, roomId) {
        resetModal();
        modalTitle.textContent = "Nova reserva";
        roomSelect.value = roomId || (rooms[0] && rooms[0].id) || "";
        titleInput.value = "";
        startInput.value = toLocalInputValue(start);
        endInput.value = toLocalInputValue(end);
        descriptionInput.value = "";
        modal.show();
    }

    function openViewModal(event) {
        resetModal();
        modalTitle.textContent = "Detalhes da reserva";
        currentBookingId = event.id;
        roomSelect.value = event.extendedProps.room_id;
        titleInput.value = event.title;
        startInput.value = toLocalInputValue(event.start);
        endInput.value = toLocalInputValue(event.end);
        descriptionInput.value = event.extendedProps.description || "";

        roomSelect.disabled = true;
        titleInput.disabled = true;
        startInput.disabled = true;
        endInput.disabled = true;
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
            right: "dayGridMonth,timeGridWeek,timeGridDay",
        },
        locale: "pt-br",
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

    saveBtn.addEventListener("click", function () {
        modalError.classList.add("d-none");
        const payload = {
            room_id: parseInt(roomSelect.value, 10),
            title: titleInput.value.trim(),
            start: startInput.value,
            end: endInput.value,
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
