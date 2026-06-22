document.addEventListener("DOMContentLoaded", function () {
    const periodSelect = document.getElementById("reportPeriod");
    const customRange = document.getElementById("reportCustomRange");
    const startInput = document.getElementById("reportStart");
    const endInput = document.getElementById("reportEnd");
    const roomSelect = document.getElementById("reportRoom");
    const errorBox = document.getElementById("reportError");
    const summaryCards = document.getElementById("reportSummaryCards");
    const roomTableBody = document.getElementById("reportRoomTable");
    const earlyStartedTableBody = document.getElementById("reportEarlyStartedTable");

    let chartByRoom = null;
    let chartByOrganizer = null;

    function formatHour(isoString) {
        return new Date(isoString).toLocaleString("pt-BR", {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function card(label, value) {
        const col = document.createElement("div");
        col.className = "col-sm-6 col-lg-3";
        col.innerHTML = `
            <div class="card h-100">
                <div class="card-body">
                    <div class="text-muted small">${label}</div>
                    <div class="fs-5 fw-bold">${value}</div>
                </div>
            </div>`;
        return col;
    }

    function renderSummary(data) {
        summaryCards.innerHTML = "";
        const totals = data.totals;
        summaryCards.appendChild(card("Reservas no período", totals.bookings_count));
        summaryCards.appendChild(card("Cancelamentos", totals.cancelled_count));
        summaryCards.appendChild(
            card("Taxa de no-show", totals.no_show_rate !== null ? `${totals.no_show_rate}%` : "—")
        );
        summaryCards.appendChild(
            card(
                "Duração média",
                totals.avg_duration_minutes !== null ? `${totals.avg_duration_minutes} min` : "—"
            )
        );
        summaryCards.appendChild(
            card("Sala mais usada", data.busiest_room ? data.busiest_room.room_name : "—")
        );
        summaryCards.appendChild(
            card("Sala menos usada", data.quietest_room ? data.quietest_room.room_name : "—")
        );
        summaryCards.appendChild(
            card(
                "Quem mais reservou",
                data.top_organizer
                    ? `${data.top_organizer.display_name} (${data.top_organizer.bookings_count})`
                    : "—"
            )
        );
        summaryCards.appendChild(
            card(
                "Quem menos reservou",
                data.bottom_organizer
                    ? `${data.bottom_organizer.display_name} (${data.bottom_organizer.bookings_count})`
                    : "—"
            )
        );
    }

    function renderRoomChart(byRoom) {
        const ctx = document.getElementById("chartByRoom");
        const config = {
            type: "bar",
            data: {
                labels: byRoom.map((r) => r.room_name),
                datasets: [
                    {
                        label: "Reservas",
                        data: byRoom.map((r) => r.bookings_count),
                        backgroundColor: "#2E8B45",
                    },
                ],
            },
            options: { responsive: true, plugins: { legend: { display: false } } },
        };
        if (chartByRoom) {
            chartByRoom.data = config.data;
            chartByRoom.update();
        } else {
            chartByRoom = new Chart(ctx, config);
        }
    }

    function renderOrganizerChart(byOrganizer) {
        const top = byOrganizer.slice(0, 10);
        const ctx = document.getElementById("chartByOrganizer");
        const config = {
            type: "bar",
            data: {
                labels: top.map((o) => o.display_name),
                datasets: [
                    {
                        label: "Reservas",
                        data: top.map((o) => o.bookings_count),
                        backgroundColor: "#2B7DD9",
                    },
                ],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                plugins: { legend: { display: false } },
            },
        };
        if (chartByOrganizer) {
            chartByOrganizer.data = config.data;
            chartByOrganizer.update();
        } else {
            chartByOrganizer = new Chart(ctx, config);
        }
    }

    function renderRoomTable(byRoom) {
        roomTableBody.innerHTML = "";
        if (byRoom.length === 0) {
            roomTableBody.innerHTML = '<tr><td colspan="4" class="text-muted text-center">Sem dados.</td></tr>';
            return;
        }
        byRoom.forEach((room) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${room.room_name}</td>
                <td>${room.bookings_count}</td>
                <td>${room.occupied_hours}</td>
                <td>${room.occupancy_rate !== null ? room.occupancy_rate + "%" : "—"}</td>`;
            roomTableBody.appendChild(tr);
        });
    }

    function renderEarlyStartedTable(meetings) {
        earlyStartedTableBody.innerHTML = "";
        if (meetings.length === 0) {
            earlyStartedTableBody.innerHTML =
                '<tr><td colspan="4" class="text-muted text-center">Nenhuma reunião começou mais cedo neste período.</td></tr>';
            return;
        }
        meetings.forEach((meeting) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${meeting.room_name}</td>
                <td>${meeting.title}</td>
                <td>${formatHour(meeting.scheduled_start)}</td>
                <td>${formatHour(meeting.actual_start)}</td>`;
            earlyStartedTableBody.appendChild(tr);
        });
    }

    function loadReport() {
        const params = new URLSearchParams();
        params.set("period", periodSelect.value);
        if (periodSelect.value === "custom") {
            params.set("start", startInput.value);
            params.set("end", endInput.value);
        }
        if (roomSelect.value) {
            params.set("room_id", roomSelect.value);
        }

        errorBox.classList.add("d-none");
        fetch(`/relatorios/dados?${params.toString()}`)
            .then((resp) => resp.json().then((data) => ({ ok: resp.ok, data })))
            .then(({ ok, data }) => {
                if (!ok) {
                    errorBox.textContent = data.error || "Não foi possível carregar o relatório.";
                    errorBox.classList.remove("d-none");
                    return;
                }
                renderSummary(data);
                renderRoomChart(data.by_room);
                renderOrganizerChart(data.by_organizer);
                renderRoomTable(data.by_room);
                renderEarlyStartedTable(data.early_started_meetings);
            })
            .catch(() => {
                errorBox.textContent = "Não foi possível carregar o relatório.";
                errorBox.classList.remove("d-none");
            });
    }

    periodSelect.addEventListener("change", function () {
        customRange.classList.toggle("d-none", periodSelect.value !== "custom");
        if (periodSelect.value !== "custom") {
            loadReport();
        }
    });
    startInput.addEventListener("change", loadReport);
    endInput.addEventListener("change", loadReport);
    roomSelect.addEventListener("change", loadReport);

    loadReport();
});
