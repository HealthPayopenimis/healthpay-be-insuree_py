"""Valid non-person synthetic PNG bytes for native photo integration tests."""
import base64
from io import BytesIO
from PIL import Image


def make_png_fixture_base64(color=(30, 90, 150)):
    output = BytesIO()
    Image.new("RGB", (256, 256), color).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")
