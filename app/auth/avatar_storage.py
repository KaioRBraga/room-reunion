import os
from io import BytesIO
from uuid import uuid4

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
AVATAR_SIZE = 256


class InvalidAvatarFileError(Exception):
    """Arquivo enviado não é uma imagem válida."""


def _avatars_dir():
    avatars_dir = os.path.join(current_app.instance_path, "uploads", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)
    return avatars_dir


def _crop_to_square(image):
    width, height = image.size
    side = min(width, height)
    left = (width - side) // 2
    top = (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def save_uploaded_avatar(file_storage, old_filename=None):
    """Recorta a imagem enviada num quadrado, redimensiona e salva como avatar do usuário."""
    original_filename = file_storage.filename or ""
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidAvatarFileError("Formato não suportado. Envie um JPG, PNG ou WEBP.")

    data = file_storage.read()
    if not data:
        raise InvalidAvatarFileError("Arquivo vazio.")

    try:
        image = Image.open(BytesIO(data))
        image.load()
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
    except UnidentifiedImageError as exc:
        raise InvalidAvatarFileError("O arquivo enviado não é uma imagem válida.") from exc

    image = _crop_to_square(image)
    image = image.resize((AVATAR_SIZE, AVATAR_SIZE))

    new_filename = f"{uuid4().hex}.jpg"
    image.save(avatar_path(new_filename), format="JPEG", quality=85)

    if old_filename:
        old_path = avatar_path(old_filename)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                current_app.logger.warning("Não foi possível remover avatar antigo: %s", old_path)

    return new_filename


def avatar_path(filename):
    return os.path.join(_avatars_dir(), filename)
