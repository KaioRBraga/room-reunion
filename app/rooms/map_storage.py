import os
from io import BytesIO
from uuid import uuid4

import fitz
from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

from app.extensions import db
from app.models import FloorMap

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
PDF_RENDER_ZOOM = 2  # ~144 dpi, boa legibilidade sem gerar arquivos enormes


class InvalidMapFileError(Exception):
    """Arquivo enviado não é um PDF/JPG/PNG válido ou não pôde ser processado."""


def _maps_dir():
    maps_dir = os.path.join(current_app.instance_path, "uploads", "maps")
    os.makedirs(maps_dir, exist_ok=True)
    return maps_dir


def _render_pdf_to_png(data, dest_path):
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            if doc.page_count == 0:
                raise InvalidMapFileError("O PDF enviado não tem páginas.")
            page = doc.load_page(0)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(PDF_RENDER_ZOOM, PDF_RENDER_ZOOM))
            with open(dest_path, "wb") as f:
                f.write(pixmap.tobytes("png"))
    except InvalidMapFileError:
        raise
    except Exception as exc:
        raise InvalidMapFileError("Não foi possível ler o PDF enviado.") from exc


def _render_image_to_png(data, dest_path):
    try:
        image = Image.open(BytesIO(data))
        image.load()
        image = ImageOps.exif_transpose(image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(dest_path, format="PNG")
    except UnidentifiedImageError as exc:
        raise InvalidMapFileError("O arquivo enviado não é uma imagem válida.") from exc
    except Exception as exc:
        raise InvalidMapFileError("Não foi possível processar a imagem enviada.") from exc


def _delete_current_map_file():
    current = FloorMap.query.first()
    if current is None:
        return
    old_path = os.path.join(_maps_dir(), current.filename)
    if os.path.exists(old_path):
        try:
            os.remove(old_path)
        except OSError:
            current_app.logger.warning("Não foi possível remover o mapa antigo: %s", old_path)
    db.session.delete(current)


def save_uploaded_map(file_storage, uploaded_by):
    """Converte o arquivo enviado (PDF/JPG/PNG) em PNG e persiste como o mapa atual."""
    original_filename = file_storage.filename or ""
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidMapFileError("Formato não suportado. Envie um PDF, JPG ou PNG.")

    data = file_storage.read()
    if not data:
        raise InvalidMapFileError("Arquivo vazio.")

    new_filename = f"{uuid4().hex}.png"
    dest_path = os.path.join(_maps_dir(), new_filename)

    if ext == ".pdf":
        _render_pdf_to_png(data, dest_path)
    else:
        _render_image_to_png(data, dest_path)

    _delete_current_map_file()

    floor_map = FloorMap(
        filename=new_filename,
        original_filename=original_filename,
        uploaded_by=uploaded_by,
    )
    db.session.add(floor_map)
    db.session.commit()
    return floor_map


def map_image_path(floor_map):
    return os.path.join(_maps_dir(), floor_map.filename)
