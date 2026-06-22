document.addEventListener("DOMContentLoaded", function () {
    const revealBtn = document.getElementById("pinRevealBtn");
    if (!revealBtn) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
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
        // Ocultar de novo não precisa de senha - só mostrar precisa.
        if (revealed) {
            showHidden();
            return;
        }
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
            .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
            .then(({ ok, data }) => {
                if (!ok || !data.ok) {
                    errorBox.textContent = (data && data.error) || "Não foi possível confirmar a senha.";
                    errorBox.classList.remove("d-none");
                    return;
                }
                modal.hide();
                pinFormWrap.classList.remove("d-none");
                if (data.pin) {
                    showRevealed(data.pin);
                }
                pinFormWrap.scrollIntoView({ behavior: "smooth", block: "center" });
            })
            .catch(function () {
                errorBox.textContent = "Erro de comunicação com o servidor.";
                errorBox.classList.remove("d-none");
            });
    }

    confirmBtn.addEventListener("click", submitPassword);
    passwordInput.addEventListener("keydown", function (evt) {
        if (evt.key === "Enter") {
            evt.preventDefault();
            submitPassword();
        }
    });
});
