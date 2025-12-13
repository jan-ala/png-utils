# PNG Utils

[![Python](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.1.3-green.svg)](png_utils.py)
[![No Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)]()

A pure Python library for creating PNG images from scratch with zero dependencies. Generate PNG files with comprehensive feature support using only the Python standard library.

## Features

- 🎨 **Complete PNG Creation**: Generate PNG files with all standard color types
- 📏 **Multiple Bit Depths**: Support for 1, 2, 4, 8, and 16-bit color depths
- 🖼️ **Adam7 Interlacing**: Progressive display support
- 🔧 **Full Metadata**: Text, gamma, time, physical dimensions, color profiles
- ⚡ **Optimal Filtering**: Automatic selection of best compression filters
- 🖥️ **Image Processing**: Nearest-neighbor image enlargement
- 🚫 **Zero Dependencies**: Only Python standard library required
- 📦 **Batteries Included**: Test images and comprehensive examples

## Installation

No installation required! Just download and use:

```bash
# Download the file
wget https://raw.githubusercontent.com/jan-ala/png-utils/main/png_utils.py

# Or clone the repository
git clone https://github.com/jan-ala/png-utils.git
cd png-utils
```

## Quick Start

```python
from png_utils import create_png_from_rgb

# Create a simple RGB image
width, height = 100, 100
rgb_data = bytes([(x + y) % 256 for _ in range(3) for y in range(height) for x in range(width)])

png_bytes = create_png_from_rgb(width, height, rgb_data)

# Save to file
with open('output.png', 'wb') as f:
    f.write(png_bytes)
```

## Comprehensive Example

```python
from png_utils import create_png, COLOR_TYPE_RGB

# Create a gradient image with metadata
width, height = 200, 200
image_data = bytearray()

for y in range(height):
    for x in range(width):
        r = int(x / width * 255)
        g = int(y / height * 255)
        b = 128
        image_data.extend([r, g, b])

# Create PNG with metadata
png_data = create_png(
    width=width,
    height=height,
    image_data=bytes(image_data),
    color_type=COLOR_TYPE_RGB,
    auxiliary_chunks={
        'tEXt': ('Software', 'PNG Utils v1.1.3'),
        'tIME': 'now',  # Current timestamp
        'pHYs': (300, 300, 1),  # 300 DPI
        'gAMA': (0.45455,),  # Gamma 2.2
        'zTXt': ('Description', 'Test gradient image created with PNG Utils')
    },
    use_optimal_filter=True
)

with open('gradient_with_metadata.png', 'wb') as f:
    f.write(png_data)
```

## API Overview

### Core Functions

| Function | Description |
|----------|-------------|
| `create_png()` | Full-featured PNG creation with all options |
| `create_png_from_rgb()` | RGB PNG convenience wrapper |
| `create_png_from_grayscale()` | Grayscale PNG convenience wrapper |
| `create_png_from_rgba()` | RGBA PNG convenience wrapper |
| `create_png_from_indexed()` | Indexed color PNG convenience wrapper |
| `enlarge_image()` | Image enlargement with nearest-neighbor interpolation |

### Color Types

```python
from png_utils import (
    COLOR_TYPE_GRAYSCALE,      # 0
    COLOR_TYPE_RGB,            # 2
    COLOR_TYPE_INDEXED,        # 3
    COLOR_TYPE_GRAYSCALE_ALPHA, # 4
    COLOR_TYPE_RGBA            # 6
)
```

## Supported Bit Depths

- **1-bit**: Black & white images
- **2-bit**: 4-level grayscale
- **4-bit**: 16-level grayscale/indexed
- **8-bit**: Standard 256 levels per channel
- **16-bit**: High precision (65,536 levels per channel)

## Auxiliary Chunk Support

The library supports all standard PNG auxiliary chunks:

- **Metadata**: `tEXt`, `zTXt`, `iTXt`
- **Time**: `tIME` (creation/modification time)
- **Color**: `gAMA`, `cHRM`, `sRGB`, `iCCP`
- **Transparency**: `tRNS`
- **Physical**: `pHYs` (pixel dimensions)
- **Background**: `bKGD`
- **Significant Bits**: `sBIT`

## Image Enlargement

```python
from png_utils import enlarge_image, COLOR_TYPE_RGB

# Double the image size
enlarged_data = enlarge_image(
    width=32,
    height=32,
    image_data=original_data,
    scale_factor=2,
    color_type=COLOR_TYPE_RGB,
    bit_depth=8
)
```

## Running Tests

The module includes self-contained tests:

```bash
python png_utils.py
```

This will create three test PNG files:

- `test_rgb_meta.png` - RGB image with metadata
- `test_rgba.png` - RGBA image with alpha gradient
- `test_indexed.png` - Indexed color image with palette

## Performance Tips

1. **Optimal Filtering**: Use `use_optimal_filter=True` for better compression
2. **Interlacing**: Adam7 interlacing increases file size (use only when needed)
3. **16-bit Images**: Use only when high precision is required
4. **Palette Images**: Use indexed color for images with ≤256 colors

## PNG File Structure

A typical PNG created by this library:

``
PNG Signature (8 bytes)
IHDR Chunk (Image header)
[PLTE Chunk] (Palette, if indexed)
[Auxiliary Chunks] (Metadata, color profiles, etc.)
IDAT Chunk (Image data)
IEND Chunk (End marker)
``

## Comparison with Other Libraries

| Feature | PNG Utils | Pillow | PyPNG |
|---------|-----------|--------|-------|
| **Dependencies** | None | Required | None |
| **PNG Creation** | ✅ | ✅ | ✅ |
| **PNG Reading** | ❌ | ✅ | ✅ |
| **Metadata Support** | ✅ | Limited | Limited |
| **Adam7 Interlacing** | ✅ | ✅ | ✅ |
| **16-bit Support** | ✅ | ✅ | ✅ |

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Support

- **Issues**: [GitHub Issues](https://github.com/jan-ala/png-utils/issues)
- **Documentation**: See [docs/](docs/) directory
- **Examples**: See [examples/](examples/) directory

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=jan-ala/png-utils&type=Date)](https://star-history.com/#jan-ala/png-utils&Date)

---

**PNG Utils** - Because sometimes you just need to create PNGs without the bloat.
