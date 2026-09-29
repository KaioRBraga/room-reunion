document.addEventListener("DOMContentLoaded", function () {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : "";

    // --- PIN reveal ---
    const revealBtn = document.getElementById("pinRevealBtn");
    if (revealBtn) {
        const modal = new bootstrap.Modal(document.getElementById("pinRevealModal"));
        const passwordInput = document.getElementById("pinRevealPassword");
        const errorBox = document.getElementById("pinRevealError");
        const confirmBtn = document.getElementById("pinRevealConfirmBtn");
        const pinFormWrap = document.getElementById("pinFormWrap");
        const maskedValue = document.getElementById("pinMaskedValue");
        const eyeIcon = document.getElementById("pinEyeIcon");
        const eyeSlashIcon = document.getElementById("pinEyeSlashIcon");

        const originalMaskedText = maskedValue.textContent.trim();
        let revealed = false;

        function showHidden() {
            revealed = false;
            maskedValue.textContent = originalMaskedText;
            eyeIcon.classList.remove("d-none");
            eyeSlashIcon.classList.add("d-none");
        }

        function showRevealed(pin) {
            revealed = true;
            maskedValue.textContent = "(" + pin + ")";
            eyeIcon.classList.add("d-none");
            eyeSlashIcon.classList.remove("d-none");
        }

        revealBtn.addEventListener("click", function () {
            if (revealed) { showHidden(); return; }
            passwordInput.value = "";
            errorBox.classList.add("d-none");
            modal.show();
        });

        function submitPassword() {
            const password = passwordInput.value;
            if (!password) {
                errorBox.textContent = "Informe sua senha.";
                errorBox.classList.remove("d-none");
                return;
            }
            fetch("/profile/pin/verify-password", {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
                body: JSON.stringify({ password: password }),
            })
                .then((res) => res.json().then(
                    (data) => ({ ok: res.ok, data }),
                    () => ({ ok: false, data: {} })
                ))
                .then(({ ok, data }) => {
                    if (!ok || !data.ok) {
                        errorBox.textContent = (data && data.error) || "Não foi possível confirmar a senha.";
                        errorBox.classList.remove("d-none");
                        return;
                    }
                    modal.hide();
                    pinFormWrap.classList.remove("d-none");
                    if (data.pin) showRevealed(data.pin);
                    pinFormWrap.scrollIntoView({ behavior: "smooth", block: "center" });
                })
                .catch(function () {
                    errorBox.textContent = "Sem resposta do servidor. Verifique a conexão e tente novamente.";
                    errorBox.classList.remove("d-none");
                });
        }

        confirmBtn.addEventListener("click", submitPassword);
        passwordInput.addEventListener("keydown", function (evt) {
            if (evt.key === "Enter") { evt.preventDefault(); submitPassword(); }
        });
    }

    // --- Reconhecimento facial via webcam ---
    const faceModalEl = document.getElementById("faceModal");
    if (faceModalEl) {
        const video = document.getElementById("faceVideo");
        const canvas = document.getElementById("faceCanvas");
        const captureBtn = document.getElementById("faceCaptureBtn");
        const errorBox = document.getElementById("faceError");
        const faceBadge = document.getElementById("faceBadge");
        let stream = null;

        const checkSvg = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true"><path d="M10.97 4.97a.75.75 0 0 1 1.07 1.05l-3.99 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425z"/></svg> ';

        faceModalEl.addEventListener("show.bs.modal", async function () {
            errorBox.classList.add("d-none");
            captureBtn.disabled = false;
            captureBtn.textContent = "Capturar";
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
                video.srcObject = stream;
            } catch (err) {
                errorBox.textContent = "Não foi possível acessar a câmera: " + err.message;
                errorBox.classList.remove("d-none");
                captureBtn.disabled = true;
            }
        });

        faceModalEl.addEventListener("hidden.bs.modal", function () {
            if (stream) {
                stream.getTracks().forEach(function (t) { t.stop(); });
                stream = null;
                video.srcObject = null;
            }
        });

        captureBtn.addEventListener("click", function () {
            if (!stream) {
                errorBox.textContent = "Câmera não disponível.";
                errorBox.classList.remove("d-none");
                return;
            }
            captureBtn.disabled = true;
            captureBtn.textContent = "Enviando…";
            errorBox.classList.add("d-none");

            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext("2d").drawImage(video, 0, 0);

            canvas.toBlob(function (blob) {
                const formData = new FormData();
                formData.append("face_image", blob, "face.jpg");
                formData.append("csrf_token", csrfToken);

                fetch("/profile/face", { method: "POST", body: formData })
                    .then(function (res) { return res.json().then(function (d) { return { ok: res.ok, d }; }); })
                    .then(function ({ ok, d }) {
                        if (d.ok) {
                            bootstrap.Modal.getInstance(faceModalEl).hide();
                            faceBadge.className = "badge text-bg-success";
                            faceBadge.title = "Check-in facial disponível nos tablets";
                            faceBadge.innerHTML = checkSvg + "Rosto cadastrado";
                        } else {
                            errorBox.textContent = d.error || "Erro ao processar o rosto.";
                            errorBox.classList.remove("d-none");
                            captureBtn.disabled = false;
                            captureBtn.textContent = "Tentar novamente";
                        }
                    })
                    .catch(function () {
                        errorBox.textContent = "Erro de conexão. Tente novamente.";
                        errorBox.classList.remove("d-none");
                        captureBtn.disabled = false;
                        captureBtn.textContent = "Tentar novamente";
                    });
            }, "image/jpeg", 0.92);
        });
    }
});
