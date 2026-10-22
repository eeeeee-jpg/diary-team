import io
import unittest

from PIL import Image

from features.guest.meal_photo import MAX_SIDE, shrink


class ShrinkTest(unittest.TestCase):
    def test_shrinks_big_photo_to_jpeg(self):
        raw = io.BytesIO()
        Image.new("RGBA", (2000, 1000), (255, 200, 100, 255)).save(raw, format="PNG")
        out = shrink(raw.getvalue())
        img = Image.open(io.BytesIO(out))
        self.assertEqual(img.format, "JPEG")
        self.assertEqual(max(img.size), MAX_SIDE)

    def test_not_an_image(self):
        self.assertIsNone(shrink(b"not an image"))
        self.assertIsNone(shrink(None))


if __name__ == "__main__":
    unittest.main()
