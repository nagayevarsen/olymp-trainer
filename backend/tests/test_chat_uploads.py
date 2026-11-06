"""Файлы ученика в чате: тип определяется по содержимому, размер и число файлов ограничены."""

import base64

import pytest

from app.chat import MAX_UPLOAD_BYTES, UploadError, upload_blocks, with_uploads

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()
PDF = base64.b64encode(b"%PDF-1.4\n" + b"0" * 32).decode()


def test_image_and_pdf_become_blocks():
    blocks = upload_blocks([{"data": PNG}, {"data": PDF}])
    assert [b["type"] for b in blocks] == ["image", "document"]
    assert blocks[0]["source"]["media_type"] == "image/png"
    assert blocks[1]["source"]["media_type"] == "application/pdf"


@pytest.mark.parametrize(
    "data",
    [
        base64.b64encode(b"<script>alert(1)</script>").decode(),  # не картинка и не PDF
        "не base64!!",
        base64.b64encode(b"%PDF-" + b"0" * MAX_UPLOAD_BYTES).decode(),  # слишком большой
    ],
)
def test_bad_files_rejected(data):
    with pytest.raises(UploadError):
        upload_blocks([{"data": data}])


def test_too_many_files():
    with pytest.raises(UploadError):
        upload_blocks([{"data": PNG}] * 4)


def test_uploads_go_into_last_message():
    msgs = [
        {"role": "user", "content": "привет"},
        {"role": "assistant", "content": "да"},
        {"role": "user", "content": "реши"},
    ]
    out = with_uploads(msgs, upload_blocks([{"data": PNG}]))
    assert out[:2] == msgs[:2]
    assert out[-1]["content"][0]["type"] == "image"
    assert out[-1]["content"][-1] == {"type": "text", "text": "реши"}
