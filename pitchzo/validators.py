"""Shared image validators for the pitchzo project."""
import os

from django.core.exceptions import ValidationError

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'avif'}


def validation_error_message(e):
    """Extract first message from ValidationError for API responses."""
    if hasattr(e, 'messages') and e.messages:
        msg = e.messages[0]
        return msg if isinstance(msg, str) else str(msg)
    return str(e)


def validate_image_file(file):
    """Validate image size (max 5MB) and format (jpg, png, jpeg, webp, avif)."""
    if file is None:
        return
    if not hasattr(file, 'size') or file.size is None:
        raise ValidationError('Invalid file: size unknown')
    if file.size > MAX_IMAGE_SIZE:
        raise ValidationError(
            f'Image size must not exceed 5MB. Current size: {file.size / (1024 * 1024):.2f}MB'
        )
    name = getattr(file, 'name', None) or ''
    ext = os.path.splitext(name)[1].lstrip('.').lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f'Allowed formats: jpg, jpeg, png, webp, avif. Got: {ext or "unknown"}'
        )
