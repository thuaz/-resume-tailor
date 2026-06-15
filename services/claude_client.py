"""Claude API wrapper — JD extraction from screenshots + resume tailoring."""
import base64
import io
from typing import Iterator

import anthropic
from PIL import Image

from config import CLAUDE_MODEL
from prompts.jd_extraction import JD_EXTRACTION_SYSTEM, JD_EXTRACTION_USER
from prompts.resume_tailoring import TAILORING_SYSTEM, TAILORING_USER


def _encode_image(image_bytes: bytes) -> tuple[str, str]:
    """Resize and base64-encode an image for the Claude Vision API.

    Returns (base64_string, media_type).
    """
    img = Image.open(io.BytesIO(image_bytes))

    # Convert RGBA to RGB if needed
    if img.mode == "RGBA":
        img = img.convert("RGB")

    # Resize if the longest edge exceeds 2048px (controls token cost)
    max_dim = 2048
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img_format = img.format or "PNG"
    # Standardise on JPEG for smaller payload; PNG if transparency needed
    save_format = "JPEG" if img.mode == "RGB" else "PNG"
    img.save(buf, format=save_format, quality=85)
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")

    media_type = "image/jpeg" if save_format == "JPEG" else "image/png"
    return encoded, media_type


def extract_jd_from_screenshot(
    client: anthropic.Anthropic, image_bytes: bytes
) -> str:
    """Extract job description text from a screenshot using Claude Vision.

    Args:
        client: An initialized anthropic.Anthropic client.
        image_bytes: Raw bytes of the uploaded image file.

    Returns:
        The extracted plain-text job description.
    """
    b64_str, media_type = _encode_image(image_bytes)

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=JD_EXTRACTION_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_str,
                        },
                    },
                    {"type": "text", "text": JD_EXTRACTION_USER},
                ],
            }
        ],
    )
    return message.content[0].text


def tailor_resume_stream(
    client: anthropic.Anthropic,
    base_resume_text: str,
    jd_text: str,
    extra_instructions: str = "",
) -> Iterator[str]:
    """Stream the tailored resume from Claude.

    Args:
        client: An initialized anthropic.Anthropic client.
        base_resume_text: The user's base resume (full text).
        jd_text: The job description text.
        extra_instructions: Optional user hints (e.g. "keep it one page").

    Yields:
        Text chunks from the streaming response.
    """
    user_message = TAILORING_USER.format(
        jd_text=jd_text,
        base_resume_text=base_resume_text,
        extra_instructions=extra_instructions or "(no extra instructions)",
    )

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=64000,
        system=TAILORING_SYSTEM,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            yield text
