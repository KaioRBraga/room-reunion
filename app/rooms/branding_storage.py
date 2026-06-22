import os
from io import BytesIO
from uuid import uuid4

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_DIMENSION = 800  # logo nao precisa de mais resolucao que isso


class InvalidLogoFileError(Exception):
    """Arquivo enviado não é uma imagem válida (PNG/JPG/WEBP)."""


def _uploads_dir():
    uploads_dir = os.path.join(current_app.static_folder, "img", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    return uploads_dir


def save_uploaded_logo(file_storage):
    """Normaliza o logo enviado para PNG (preservando transparência) e salva
    com um nome único, devolvendo o filename para persistir no banco."""
    original_filename = file_storage.filename or ""
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidLogoFileError("Formato não suportado. Envie um PNG, JPG ou WEBP.")

    data = file_storage.read()
    if not data:
        raise InvalidLogoFileError("Arquivo vazio.")

    try:
        image = Image.open(BytesIO(data))
        image.load()
        image = ImageOps.exif_transpose(image)
    except UnidentifiedImageError as exc:
        raise InvalidLogoFileError("O arquivo enviado não é uma imagem válida.") from exc

    if image.mode not in ("RGBA", "RGB"):
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")

    if max(image.size) > MAX_DIMENSION:
        image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

    new_filename = f"{uuid4().hex}.png"
    image.save(os.path.join(_uploads_dir(), new_filename), format="PNG")
    return new_filename


def delete_logo_file(filename):
    if not filename:
        return
    path = os.path.join(_uploads_dir(), filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            current_app.logger.warning("Não foi possível remover o logo antigo: %s", path)
