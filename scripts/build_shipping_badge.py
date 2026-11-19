"""Build the distributable PNG once; deployment needs no Japanese font."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    image = Image.new("RGBA", (660, 190), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 659, 189), radius=24, fill="#657443")
    font = ImageFont.truetype("C:/Windows/Fonts/meiryob.ttc", 116)
    draw.text((330, 95), "送料無料", font=font, fill="white", anchor="mm")
    target = Path(__file__).resolve().parents[1] / "assets/listing_overlay/free_shipping.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)


if __name__ == "__main__":
    main()
