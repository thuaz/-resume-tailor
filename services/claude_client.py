"""DeepSeek API wrapper — JD extraction from screenshots + resume tailoring.

Uses the OpenAI-compatible DeepSeek API. DeepSeek-V3 (deepseek-chat) supports
vision for screenshot extraction and long-context text generation for resumes.
"""
import base64
import io
from typing import Iterator

from openai import OpenAI
from PIL import Image

from config import DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from prompts.jd_extraction import JD_EXTRACTION_SYSTEM, JD_EXTRACTION_USER
from prompts.resume_generation import GENERATE_RESUME_SYSTEM, GENERATE_RESUME_USER
from prompts.resume_tailoring import TAILORING_SYSTEM, TAILORING_USER


def _build_client(api_key: str) -> OpenAI:
    """Create an OpenAI client pointed at DeepSeek's API."""
    return OpenAI(base_url=DEEPSEEK_BASE_URL, api_key=api_key)


def _encode_image(image_bytes: bytes) -> str:
    """Resize and encode an image as a data: URL for the DeepSeek Vision API.

    Returns a data:image/jpeg;base64,... string.
    """
    img = Image.open(io.BytesIO(image_bytes))

    if img.mode == "RGBA":
        img = img.convert("RGB")

    # Resize if longest edge exceeds 2048px (controls token cost)
    max_dim = 2048
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")

    return f"data:image/jpeg;base64,{encoded}"


# ── JD Extraction ──────────────────────────────────────────────────────────


def extract_jd_from_screenshot(api_key: str, image_bytes: bytes) -> str:
    """Extract job description text from a screenshot using DeepSeek Vision.

    Args:
        api_key: DeepSeek API key.
        image_bytes: Raw bytes of the uploaded image file.

    Returns:
        The extracted plain-text job description.
    """
    client = _build_client(api_key)
    data_url = _encode_image(image_bytes)

    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": JD_EXTRACTION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": JD_EXTRACTION_USER},
                ],
            },
        ],
    )
    return response.choices[0].message.content


# ── Resume Tailoring ───────────────────────────────────────────────────────


def tailor_resume_stream(
    api_key: str,
    base_resume_text: str,
    jd_text: str,
    extra_instructions: str = "",
) -> Iterator[str]:
    """Stream the tailored resume from DeepSeek.

    Args:
        api_key: DeepSeek API key.
        base_resume_text: The user's base resume (full text).
        jd_text: The job description text.
        extra_instructions: Optional user hints (e.g. "keep it one page").

    Yields:
        Text chunks from the streaming response.
    """
    client = _build_client(api_key)

    user_message = TAILORING_USER.format(
        jd_text=jd_text,
        base_resume_text=base_resume_text,
        extra_instructions=extra_instructions or "(no extra instructions)",
    )

    stream = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": TAILORING_SYSTEM},
            {"role": "user", "content": user_message},
        ],
        stream=True,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


# ── Resume Generation from Description ─────────────────────────────────────


def generate_resume_stream(
    api_key: str,
    description: str,
) -> Iterator[str]:
    """Generate a formal base resume from a casual self-description.

    Args:
        api_key: DeepSeek API key.
        description: Casual self-description text.

    Yields:
        Text chunks from the streaming response.
    """
    client = _build_client(api_key)
    user_message = GENERATE_RESUME_USER.format(description=description)

    stream = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": GENERATE_RESUME_SYSTEM},
            {"role": "user", "content": user_message},
        ],
        stream=True,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
