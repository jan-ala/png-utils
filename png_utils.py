'''
png_utils.py - PNG file creation utilities

Features:
1. Create PNG chunks (supports all color types and bit depths)
2. Adam7 interlacing support
3. Complete PNG file generation
4. No decoding/parsing functions
'''

import struct
import zlib
import warnings
from typing import List, Tuple, Optional, Union, Dict, Any

# ==================== Constants ====================

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

# Color type constants
COLOR_TYPE_GRAYSCALE = 0      # Grayscale
COLOR_TYPE_RGB = 2            # Truecolor (RGB)
COLOR_TYPE_INDEXED = 3        # Indexed color
COLOR_TYPE_GRAYSCALE_ALPHA = 4  # Grayscale with alpha
COLOR_TYPE_RGBA = 6           # Truecolor with alpha (RGBA)

__version__  = '1.1.4'

# ==================== Image Enlargement Functions ====================

def enlarge_image(width: int, height: int,
                  image_data: bytes, scale_factor: int,
                  color_type: int, bit_depth: int) -> bytes:
    '''
    Enlarge an image by a specified scale factor using nearest-neighbor interpolation.
    
    Args:
        width: Original image width in pixels
        height: Original image height in pixels
        image_data: Original image pixel data
        scale_factor: Integer scaling factor (e.g., 2 = 200% enlargement)
        color_type: PNG color type (0=grayscale, 2=RGB, 6=RGBA, etc.)
        bit_depth: Bit depth (1, 2, 4, 8, or 16)
    
    Returns:
        bytes: Enlarged image pixel data
    
    Raises:
        ValueError: If scale_factor is not a positive integer
        ValueError: If image_data size doesn't match width, height, color_type and bit_depth
    '''
    # Validate scale factor
    if scale_factor < 1:
        raise ValueError("'scale_factor' must be a positive integer")
    if scale_factor == 1:
        return image_data  # No scaling needed
    
    # Calculate new dimensions
    new_width = width * scale_factor
    new_height = height * scale_factor
    
    # Handle different color types
    if color_type == COLOR_TYPE_INDEXED:
        # For indexed color: data is packed for bit depths < 8
        return _enlarge_indexed(width, height, image_data, scale_factor, bit_depth)
    
    elif color_type == COLOR_TYPE_GRAYSCALE:
        if bit_depth < 8:
            # For low-bit-depth grayscale: data is packed
            return _enlarge_grayscale_low_bit_depth(width, height, image_data, scale_factor, bit_depth)
        else:
            # For 8/16-bit grayscale
            bytes_per_pixel = 1 if bit_depth == 8 else 2
            return _enlarge_standard(width, height, image_data, scale_factor, bytes_per_pixel)
    
    elif color_type == COLOR_TYPE_RGB:
        if bit_depth == 8:
            bytes_per_pixel = 3
            return _enlarge_standard(width, height, image_data, scale_factor, bytes_per_pixel)
        elif bit_depth == 16:
            bytes_per_pixel = 6
            return _enlarge_standard(width, height, image_data, scale_factor, bytes_per_pixel)
        else:
            raise ValueError(f'RGB color type does not support bit depth {bit_depth}')
    
    elif color_type == COLOR_TYPE_RGBA:
        if bit_depth == 8:
            bytes_per_pixel = 4
            return _enlarge_standard(width, height, image_data, scale_factor, bytes_per_pixel)
        elif bit_depth == 16:
            bytes_per_pixel = 8
            return _enlarge_standard(width, height, image_data, scale_factor, bytes_per_pixel)
        else:
            raise ValueError(f'RGBA color type does not support bit depth {bit_depth}')
    
    elif color_type == COLOR_TYPE_GRAYSCALE_ALPHA:
        if bit_depth == 8:
            bytes_per_pixel = 2
            return _enlarge_standard(width, height, image_data, scale_factor, bytes_per_pixel)
        elif bit_depth == 16:
            bytes_per_pixel = 4
            return _enlarge_standard(width, height, image_data, scale_factor, bytes_per_pixel)
        else:
            raise ValueError(f'Grayscale+Alpha color type does not support bit depth {bit_depth}')
    
    else:
        raise ValueError(f'unsupported color type: {color_type}')


def _enlarge_standard(width: int, height: int,
                     image_data: bytes, scale_factor: int,
                     bytes_per_pixel: int) -> bytes:
    '''
    Enlarge standard 8-bit or 16-bit image data
    '''
    new_width = width * scale_factor
    new_height = height * scale_factor
    
    # Validate data size
    expected_size = width * height * bytes_per_pixel
    if len(image_data) != expected_size:
        raise ValueError(
            f'Expected {expected_size} bytes for {width}x{height} image '
            f'with {bytes_per_pixel} bytes per pixel, got {len(image_data)} bytes'
        )
    
    output = bytearray(new_width * new_height * bytes_per_pixel)
    
    for y in range(height):
        for x in range(width):
            # Get source pixel
            src_index = (y * width + x) * bytes_per_pixel
            src_pixel = image_data[src_index:src_index + bytes_per_pixel]
            
            # Copy pixel to all scaled positions
            for dy in range(scale_factor):
                for dx in range(scale_factor):
                    dest_y = y * scale_factor + dy
                    dest_x = x * scale_factor + dx
                    dest_index = (dest_y * new_width + dest_x) * bytes_per_pixel
                    output[dest_index:dest_index + bytes_per_pixel] = src_pixel
    
    return bytes(output)


def _enlarge_indexed(width: int, height: int,
                    image_data: bytes, scale_factor: int,
                    bit_depth: int) -> bytes:
    '''
    Enlarge indexed color image data (supports all bit depths: 1, 2, 4, 8)
    '''
    new_width = width * scale_factor
    new_height = height * scale_factor
    
    if bit_depth == 8:
        # For 8-bit indexed: 1 byte per pixel
        expected_size = width * height
        if len(image_data) != expected_size:
            raise ValueError(
                f'Expected {expected_size} bytes for {width}x{height} 8-bit indexed image, '
                f'got {len(image_data)} bytes'
            )
        
        output = bytearray(new_width * new_height)
        
        for y in range(height):
            for x in range(width):
                src_index = y * width + x
                src_pixel = image_data[src_index]
                
                # Copy pixel to all scaled positions
                for dy in range(scale_factor):
                    for dx in range(scale_factor):
                        dest_y = y * scale_factor + dy
                        dest_x = x * scale_factor + dx
                        dest_index = dest_y * new_width + dest_x
                        output[dest_index] = src_pixel
        
        return bytes(output)
    
    else:
        # For low-bit-depth indexed (1, 2, 4 bits): data is packed
        pixels_per_byte = 8 // bit_depth
        mask = (1 << bit_depth) - 1
        
        # Validate data size
        bytes_per_row = (width + pixels_per_byte - 1) // pixels_per_byte
        expected_size = bytes_per_row * height
        
        if len(image_data) != expected_size:
            raise ValueError(
                f'Expected {expected_size} bytes for {width}x{height} {bit_depth}-bit indexed image, '
                f'got {len(image_data)} bytes'
            )
        
        # First unpack to full bytes for easier processing
        unpacked = bytearray(width * height)
        
        for y in range(height):
            row_start = y * bytes_per_row
            for x in range(width):
                byte_index = row_start + x // pixels_per_byte
                if byte_index < len(image_data):
                    byte = image_data[byte_index]
                    shift = 8 - ((x % pixels_per_byte) + 1) * bit_depth
                    pixel_value = (byte >> shift) & mask
                    unpacked[y * width + x] = pixel_value
        
        # Enlarge the unpacked data
        enlarged_unpacked = bytearray(new_width * new_height)
        
        for y in range(height):
            for x in range(width):
                src_index = y * width + x
                src_pixel = unpacked[src_index]
                
                # Copy pixel to all scaled positions
                for dy in range(scale_factor):
                    for dx in range(scale_factor):
                        dest_y = y * scale_factor + dy
                        dest_x = x * scale_factor + dx
                        dest_index = dest_y * new_width + dest_x
                        enlarged_unpacked[dest_index] = src_pixel
        
        # Pack back to original bit depth
        return _pack_pixels_to_bytes(enlarged_unpacked, bit_depth)


def _enlarge_grayscale_low_bit_depth(width: int, height: int,
                                    image_data: bytes, scale_factor: int,
                                    bit_depth: int) -> bytes:
    '''
    Enlarge low-bit-depth grayscale image data (1, 2, or 4 bits per pixel)
    '''
    new_width = width * scale_factor
    new_height = height * scale_factor
    
    pixels_per_byte = 8 // bit_depth
    mask = (1 << bit_depth) - 1
    
    # Validate data size
    bytes_per_row = (width + pixels_per_byte - 1) // pixels_per_byte
    expected_size = bytes_per_row * height
    
    if len(image_data) != expected_size:
        raise ValueError(
            f'Expected {expected_size} bytes for {width}x{height} {bit_depth}-bit grayscale image, '
            f'got {len(image_data)} bytes'
        )
    
    # First unpack to full bytes (scaled to 8-bit for enlargement)
    unpacked_8bit = bytearray(width * height)
    
    for y in range(height):
        row_start = y * bytes_per_row
        for x in range(width):
            byte_index = row_start + x // pixels_per_byte
            if byte_index < len(image_data):
                byte = image_data[byte_index]
                shift = 8 - ((x % pixels_per_byte) + 1) * bit_depth
                pixel_value = (byte >> shift) & mask
                
                # Scale to 8-bit range
                if bit_depth == 1:
                    unpacked_8bit[y * width + x] = 0 if pixel_value == 0 else 255
                elif bit_depth == 2:
                    unpacked_8bit[y * width + x] = pixel_value * 85  # 0, 85, 170, 255
                elif bit_depth == 4:
                    unpacked_8bit[y * width + x] = pixel_value * 17  # 0, 17, 34, ..., 255
    
    # Enlarge the 8-bit data
    enlarged_8bit = bytearray(new_width * new_height)
    
    for y in range(height):
        for x in range(width):
            src_index = y * width + x
            src_pixel = unpacked_8bit[src_index]
            
            # Copy pixel to all scaled positions
            for dy in range(scale_factor):
                for dx in range(scale_factor):
                    dest_y = y * scale_factor + dy
                    dest_x = x * scale_factor + dx
                    dest_index = dest_y * new_width + dest_x
                    enlarged_8bit[dest_index] = src_pixel
    
    # Convert back to original bit depth
    return _pack_pixels_to_bytes_low_bit_depth_grayscale(enlarged_8bit, bit_depth)


def _pack_pixels_to_bytes(pixel_values: bytes, bit_depth: int) -> bytes:
    '''
    Pack pixel values into bytes (for low bit depths: 1, 2, 4 bits)
    
    Args:
        pixel_values: Bytes of pixel values (each byte contains one pixel value)
        bit_depth: Bit depth (1, 2, 4)
    
    Returns:
        Packed bytes
    '''
    if bit_depth == 8:
        return pixel_values
    
    pixels_per_byte = 8 // bit_depth
    mask = (1 << bit_depth) - 1
    result = bytearray()
    current_byte = 0
    bits_filled = 0
    
    for pixel in pixel_values:
        current_byte = (current_byte << bit_depth) | (pixel & mask)
        bits_filled += bit_depth
        
        if bits_filled == 8:
            result.append(current_byte)
            current_byte = 0
            bits_filled = 0
    
    if bits_filled > 0:
        current_byte <<= (8 - bits_filled)
        result.append(current_byte)
    
    return bytes(result)


def _pack_pixels_to_bytes_low_bit_depth_grayscale(pixel_values_8bit: bytes, bit_depth: int) -> bytes:
    '''
    Convert 8-bit grayscale values back to low bit depth packed bytes
    
    Args:
        pixel_values_8bit: 8-bit grayscale pixel values
        bit_depth: Target bit depth (1, 2, 4)
    
    Returns:
        Packed bytes in specified bit depth
    '''
    pixels_per_byte = 8 // bit_depth
    result = bytearray()
    current_byte = 0
    bits_filled = 0
    
    for pixel_8bit in pixel_values_8bit:
        # Convert 8-bit value back to low bit depth
        if bit_depth == 1:
            pixel_value = 0 if pixel_8bit < 128 else 1
        elif bit_depth == 2:
            pixel_value = min(pixel_8bit // 85, 3)  # 0-3
        elif bit_depth == 4:
            pixel_value = min(pixel_8bit // 17, 15)  # 0-15
        else:
            pixel_value = pixel_8bit >> (8 - bit_depth)  # For theoretical bit depths
        
        current_byte = (current_byte << bit_depth) | pixel_value
        bits_filled += bit_depth
        
        if bits_filled == 8:
            result.append(current_byte)
            current_byte = 0
            bits_filled = 0
    
    if bits_filled > 0:
        current_byte <<= (8 - bits_filled)
        result.append(current_byte)
    
    return bytes(result)

# ==================== Core Chunk Creation ====================

def create_png_chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
    '''
    Create a PNG chunk
    
    Args:
        chunk_type: 4-byte chunk type, e.g., b'IHDR', b'IDAT', b'IEND'
        chunk_data: Chunk data
    
    Returns:
        Complete PNG chunk as bytes
    '''
    if not isinstance(chunk_type, bytes):
        raise TypeError("chunk_type must be a 'bytes' object")
    if not isinstance(chunk_data, bytes):
        raise TypeError("chunk_data must be a 'bytes' object")
    if len(chunk_type) != 4:
        raise ValueError('chunk_type must be 4 bytes')
    
    length = len(chunk_data)
    return struct.pack(f'>I4s{length}sI',
                       length,
                       chunk_type,
                       chunk_data,
                       zlib.crc32(chunk_type + chunk_data) & 0xffffffff)

def create_IHDR(width: int, height: int,
                bit_depth: int = 8,
                color_type: int = COLOR_TYPE_RGB,
                interlace_method: int = 0) -> bytes:
    '''
    Create IHDR chunk
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        bit_depth: Bit depth (1, 2, 4, 8, or 16)
        color_type: Color type (0, 2, 3, 4, or 6)
        interlace_method: Interlace method (0=none, 1=Adam7)
    
    Returns:
        IHDR chunk bytes
    '''
    if width <= 0 or height <= 0:
        raise ValueError("'width' and 'height' must be positive integers")
    
    valid_bit_depths = {1, 2, 4, 8, 16}
    if bit_depth not in valid_bit_depths:
        raise ValueError(f"'bit_depth' must be one of {sorted(valid_bit_depths)}")
    
    valid_color_types = {0, 2, 3, 4, 6}
    if color_type not in valid_color_types:
        raise ValueError(f"'color_type' must be one of {sorted(valid_color_types)}")
    
    if color_type == COLOR_TYPE_INDEXED and bit_depth == 16:
        raise ValueError('indexed color (3) does not support 16-bit depth')
    
    if interlace_method not in (0, 1):
        raise ValueError("'interlace_method' must be 0 (none) or 1 (Adam7)")
    
    if interlace_method == 1:
        warnings.warn(
            'Adam7 interlacing increases file size. Use interlace_method=0 for optimal results.',
            UserWarning
        )
    
    ihdr_data = struct.pack('>IIBBBBB',
                           width, height,
                           bit_depth, color_type,
                           0, 0, interlace_method)
    
    return create_png_chunk(b'IHDR', ihdr_data)

def create_IEND() -> bytes:
    '''
    Create IEND chunk (hardcoded for efficiency)
    '''
    return b'\x00\x00\x00\x00IEND\xaeB`\x82'

# ==================== Auxiliary Chunk Functions ====================

def create_PLTE(palette: List[Tuple[int, int, int]]) -> bytes:
    '''
    Create PLTE (palette) chunk
    
    Args:
        palette: List of RGB tuples [(r,g,b), ...], max 256 colors
    
    Returns:
        PLTE chunk bytes
    '''
    if not palette:
        raise ValueError("'palette' cannot be empty")
    
    if len(palette) > 256:
        raise ValueError("'palette' can have at most 256 colors")
    
    data = bytearray()
    for r, g, b in palette:
        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
            raise ValueError('RGB values must be in range 0-255')
        data.extend([r, g, b])
    
    return create_png_chunk(b'PLTE', bytes(data))

def create_tRNS(alpha_values: List[int]) -> bytes:
    '''
    Create tRNS (transparency) chunk
    
    Args:
        alpha_values: List of alpha values (0-255)
    
    Returns:
        tRNS chunk bytes
    '''
    if not alpha_values:
        raise ValueError("'alpha_values' cannot be empty")
    
    for alpha in alpha_values:
        if not (0 <= alpha <= 255):
            raise ValueError('alpha values must be in range 0-255')
    
    data = struct.pack(f'>{len(alpha_values)}B', *alpha_values)
    return create_png_chunk(b'tRNS', data)

def create_gAMA(gamma: float) -> bytes:
    '''
    Create gamma correction chunk
    
    Args:
        gamma: Gamma value (typically 0.45455 for gamma 2.2)
    
    Returns:
        gAMA chunk bytes
    '''
    if gamma <= 0:
        raise ValueError('gamma must be positive')
    
    # Store as integer multiplied by 100000
    gamma_int = int(gamma * 100000)
    if gamma_int == 0:
        gamma_int = 1  # Minimum non-zero value
    
    data = struct.pack('>I', gamma_int)
    return create_png_chunk(b'gAMA', data)

def create_cHRM(white_point_x: float, white_point_y: float,
               red_x: float, red_y: float,
               green_x: float, green_y: float,
               blue_x: float, blue_y: float) -> bytes:
    '''
    Create chromaticities chunk
    
    Args:
        white_point_x, white_point_y: Reference white point coordinates (0-0.8)
        red_x, red_y: Red primary coordinates
        green_x, green_y: Green primary coordinates
        blue_x, blue_y: Blue primary coordinates
    
    Returns:
        cHRM chunk bytes
    '''
    # Validate coordinate ranges
    for name, value in [('white_point_x', white_point_x), ('white_point_y', white_point_y),
                       ('red_x', red_x), ('red_y', red_y),
                       ('green_x', green_x), ('green_y', green_y),
                       ('blue_x', blue_x), ('blue_y', blue_y)]:
        if not (0 <= value <= 0.8):
            raise ValueError(f"'{name}' must be between 0 and 0.8")
    
    # Pack all coordinates multiplied by 100000
    data = struct.pack('>IIIIIIII',
                      int(white_point_x * 100000),
                      int(white_point_y * 100000),
                      int(red_x * 100000),
                      int(red_y * 100000),
                      int(green_x * 100000),
                      int(green_y * 100000),
                      int(blue_x * 100000),
                      int(blue_y * 100000))
    return create_png_chunk(b'cHRM', data)

def create_sRGB(rendering_intent: int) -> bytes:
    '''
    Create sRGB color space chunk
    
    Args:
        rendering_intent: Rendering intent
            0: Perceptual (for photographs)
            1: Relative colorimetric (for logos)
            2: Saturation (for graphics)
            3: Absolute colorimetric (for proofing)
    
    Returns:
        sRGB chunk bytes
    '''
    if rendering_intent not in (0, 1, 2, 3):
        raise ValueError('rendering intent must be 0, 1, 2, or 3')
    
    data = struct.pack('>B', rendering_intent)
    return create_png_chunk(b'sRGB', data)

def create_iCCP(profile_name: str, compressed_profile: bytes) -> bytes:
    '''
    Create ICC profile chunk
    
    Args:
        profile_name: Profile name (1-79 characters)
        compressed_profile: Compressed ICC profile data
    
    Returns:
        iCCP chunk bytes
    '''
    if not (1 <= len(profile_name) <= 79):
        raise ValueError('profile name must be 1-79 characters')
    if '\x00' in profile_name:
        raise ValueError('profile name cannot contain null byte')
    
    name_bytes = profile_name.encode('latin-1')
    # Format: name + null + compression method (0) + compressed data
    data = name_bytes + b'\x00' + b'\x00' + compressed_profile
    return create_png_chunk(b'iCCP', data)

def create_tEXt(keyword: str, text: str) -> bytes:
    '''
    Create text chunk (ISO-8859-1 encoding)
    
    Args:
        keyword: Keyword (1-79 characters)
        text: Text content
    
    Returns:
        tEXt chunk bytes
    '''
    if not (1 <= len(keyword) <= 79):
        raise ValueError('keyword must be 1-79 characters')
    if '\x00' in keyword:
        raise ValueError('keyword cannot contain null byte')
    
    keyword_bytes = keyword.encode('latin-1')
    text_bytes = text.encode('latin-1')  # ISO-8859-1
    data = keyword_bytes + b'\x00' + text_bytes
    return create_png_chunk(b'tEXt', data)

def create_zTXt(keyword: str, text: str) -> bytes:
    '''
    Create compressed text chunk
    
    Args:
        keyword: Keyword (1-79 characters)
        text: Text content (will be compressed)
    
    Returns:
        zTXt chunk bytes
    '''
    if not (1 <= len(keyword) <= 79):
        raise ValueError('keyword must be 1-79 characters')
    if '\x00' in keyword:
        raise ValueError('keyword cannot contain null byte')
    
    keyword_bytes = keyword.encode('latin-1')
    text_bytes = text.encode('utf-8')
    compressed_text = zlib.compress(text_bytes)
    
    # Format: keyword + null + compression method (0) + compressed text
    data = keyword_bytes + b'\x00\x00' + compressed_text
    return create_png_chunk(b'zTXt', data)

def create_iTXt(keyword: str, text: str,
               language_tag: str = '',
               translated_keyword: str = '',
               compressed: bool = False) -> bytes:
    '''
    Create international text chunk (UTF-8 encoding)
    
    Args:
        keyword: Keyword (1-79 characters)
        text: Text content (UTF-8)
        language_tag: RFC-3066 language tag (e.g., 'en', 'zh-CN')
        translated_keyword: Translated keyword
        compressed: Whether to compress the text
    
    Returns:
        iTXt chunk bytes
    '''
    if not (1 <= len(keyword) <= 79):
        raise ValueError('keyword must be 1-79 characters')
    if '\x00' in keyword:
        raise ValueError('keyword cannot contain null byte')
    
    keyword_bytes = keyword.encode('latin-1')
    language_bytes = language_tag.encode('utf-8')
    translated_bytes = translated_keyword.encode('utf-8')
    
    # Prepare text data
    text_bytes = text.encode('utf-8')
    if compressed:
        text_bytes = zlib.compress(text_bytes)
    
    # Build data: keyword + compression flag + compression method + language + translated keyword + text
    data = bytearray()
    data.extend(keyword_bytes)
    data.append(1 if compressed else 0)  # Compression flag
    data.append(0)  # Compression method (0=zlib, only if compressed)
    data.extend(language_bytes)
    data.append(0)  # Null separator
    data.extend(translated_bytes)
    data.append(0)  # Null separator
    data.extend(text_bytes)
    
    return create_png_chunk(b'iTXt', bytes(data))

def create_bKGD_for_grayscale(gray_value: int) -> bytes:
    '''
    Create background color chunk for grayscale images
    
    Args:
        gray_value: Gray value (0-65535 for 16-bit, 0-255 for 8-bit)
    
    Returns:
        bKGD chunk bytes
    '''
    if not (0 <= gray_value <= 65535):
        raise ValueError('gray value must be 0-65535')
    
    data = struct.pack('>H', gray_value)
    return create_png_chunk(b'bKGD', data)

def create_bKGD_for_rgb(red: int, green: int, blue: int) -> bytes:
    '''
    Create background color chunk for RGB images
    
    Args:
        red: Red value (0-65535)
        green: Green value (0-65535)
        blue: Blue value (0-65535)
    
    Returns:
        bKGD chunk bytes
    '''
    for name, value in [('red', red), ('green', green), ('blue', blue)]:
        if not (0 <= value <= 65535):
            raise ValueError(f'{name} value must be 0-65535')
    
    data = struct.pack('>HHH', red, green, blue)
    return create_png_chunk(b'bKGD', data)

def create_bKGD_for_indexed(palette_index: int) -> bytes:
    '''
    Create background color chunk for indexed color images
    
    Args:
        palette_index: Palette index (0-255)
    
    Returns:
        bKGD chunk bytes
    '''
    if not (0 <= palette_index <= 255):
        raise ValueError('palette index must be 0-255')
    
    data = struct.pack('>B', palette_index)
    return create_png_chunk(b'bKGD', data)

def create_pHYs(pixels_per_unit_x: int, pixels_per_unit_y: int,
               unit_specifier: int = 1) -> bytes:
    '''
    Create physical pixel dimensions chunk
    
    Args:
        pixels_per_unit_x: Pixels per unit in X direction
        pixels_per_unit_y: Pixels per unit in Y direction
        unit_specifier: Unit specifier (0=unknown, 1=meter)
    
    Returns:
        pHYs chunk bytes
    '''
    if unit_specifier not in (0, 1):
        raise ValueError('unit specifier must be 0 or 1')
    if pixels_per_unit_x < 0 or pixels_per_unit_y < 0:
        raise ValueError('pixels per unit cannot be negative')
    
    data = struct.pack('>IIB', pixels_per_unit_x, pixels_per_unit_y, unit_specifier)
    return create_png_chunk(b'pHYs', data)

def create_sBIT_for_grayscale(gray_bits: int) -> bytes:
    '''
    Create significant bits chunk for grayscale images
    
    Args:
        gray_bits: Number of significant bits in grayscale data
    
    Returns:
        sBIT chunk bytes
    '''
    if not (1 <= gray_bits <= 16):
        raise ValueError('gray bits must be 1-16')
    
    data = struct.pack('>B', gray_bits)
    return create_png_chunk(b'sBIT', data)

def create_sBIT_for_rgb(red_bits: int, green_bits: int, blue_bits: int) -> bytes:
    '''
    Create significant bits chunk for RGB images
    
    Args:
        red_bits: Number of significant bits in red channel
        green_bits: Number of significant bits in green channel
        blue_bits: Number of significant bits in blue channel
    
    Returns:
        sBIT chunk bytes
    '''
    for name, value in [('red_bits', red_bits), ('green_bits', green_bits), ('blue_bits', blue_bits)]:
        if not (1 <= value <= 16):
            raise ValueError(f"'{name}' must be 1-16")
    
    data = struct.pack('>BBB', red_bits, green_bits, blue_bits)
    return create_png_chunk(b'sBIT', data)

def create_sBIT_for_indexed(palette_bits: int) -> bytes:
    '''
    Create significant bits chunk for indexed color images
    
    Args:
        palette_bits: Number of significant bits in palette
    
    Returns:
        sBIT chunk bytes
    '''
    if not (1 <= palette_bits <= 8):
        raise ValueError('palette bits must be 1-8')
    
    data = struct.pack('>BBB', palette_bits, palette_bits, palette_bits)
    return create_png_chunk(b'sBIT', data)

def create_sBIT_for_grayscale_alpha(gray_bits: int, alpha_bits: int) -> bytes:
    '''
    Create significant bits chunk for grayscale+alpha images
    
    Args:
        gray_bits: Number of significant bits in grayscale
        alpha_bits: Number of significant bits in alpha
    
    Returns:
        sBIT chunk bytes
    '''
    if not (1 <= gray_bits <= 16):
        raise ValueError('gray bits must be 1-16')
    if not (1 <= alpha_bits <= 16):
        raise ValueError('alpha bits must be 1-16')
    
    data = struct.pack('>BB', gray_bits, alpha_bits)
    return create_png_chunk(b'sBIT', data)

def create_sBIT_for_rgba(red_bits: int, green_bits: int, blue_bits: int, alpha_bits: int) -> bytes:
    '''
    Create significant bits chunk for RGBA images
    
    Args:
        red_bits: Number of significant bits in red channel
        green_bits: Number of significant bits in green channel
        blue_bits: Number of significant bits in blue channel
        alpha_bits: Number of significant bits in alpha channel
    
    Returns:
        sBIT chunk bytes
    '''
    for name, value in [('red_bits', red_bits), ('green_bits', green_bits),
                       ('blue_bits', blue_bits), ('alpha_bits', alpha_bits)]:
        if not (1 <= value <= 16):
            raise ValueError(f"'{name}' must be 1-16")
    
    data = struct.pack('>BBBB', red_bits, green_bits, blue_bits, alpha_bits)
    return create_png_chunk(b'sBIT', data)

def create_tIME(year: int, month: int, day: int,
               hour: int, minute: int, second: int) -> bytes:
    '''
    Create last modification time chunk (UTC)
    
    Args:
        year: Year (e.g., 2024)
        month: Month (1-12)
        day: Day (1-31)
        hour: Hour (0-23)
        minute: Minute (0-59)
        second: Second (0-60, 60 for leap seconds)
    
    Returns:
        tIME chunk bytes
    '''
    # Validate date/time
    if year < 0 or year > 65535:
        raise ValueError('year must be 0-65535')
    if not (1 <= month <= 12):
        raise ValueError('month must be 1-12')
    if not (1 <= day <= 31):
        raise ValueError('day must be 1-31')
    if not (0 <= hour <= 23):
        raise ValueError('hour must be 0-23')
    if not (0 <= minute <= 59):
        raise ValueError('minute must be 0-59')
    if not (0 <= second <= 60):
        raise ValueError('second must be 0-60')
    
    data = struct.pack('>HBBBBB', year, month, day, hour, minute, second)
    return create_png_chunk(b'tIME', data)

def create_tIME_now() -> bytes:
    '''
    Create tIME chunk with current UTC time
    
    Returns:
        tIME chunk bytes
    '''
    import time
    now = time.gmtime()
    return create_tIME(now.tm_year, now.tm_mon, now.tm_mday,
                      now.tm_hour, now.tm_min, now.tm_sec)

# ==================== Convenience Functions ====================

def create_bKGD(color_type: int, *args) -> bytes:
    '''
    Create background color chunk (convenience wrapper)
    
    Args:
        color_type: PNG color type
        *args: Depends on color_type:
            COLOR_TYPE_GRAYSCALE: gray_value (int)
            COLOR_TYPE_RGB: red, green, blue (int)
            COLOR_TYPE_INDEXED: palette_index (int)
            COLOR_TYPE_GRAYSCALE_ALPHA: gray_value (int)
            COLOR_TYPE_RGBA: red, green, blue (int)
    
    Returns:
        bKGD chunk bytes
    '''
    if color_type == COLOR_TYPE_GRAYSCALE or color_type == COLOR_TYPE_GRAYSCALE_ALPHA:
        if len(args) != 1:
            raise ValueError('grayscale requires 1 argument: gray_value')
        return create_bKGD_for_grayscale(args[0])
    elif color_type == COLOR_TYPE_RGB or color_type == COLOR_TYPE_RGBA:
        if len(args) != 3:
            raise ValueError('RGB requires 3 arguments: red, green, blue')
        return create_bKGD_for_rgb(args[0], args[1], args[2])
    elif color_type == COLOR_TYPE_INDEXED:
        if len(args) != 1:
            raise ValueError('indexed requires 1 argument: palette_index')
        return create_bKGD_for_indexed(args[0])
    else:
        raise ValueError(f'unsupported color type for bKGD: {color_type}')

def create_sBIT(color_type: int, *args) -> bytes:
    '''
    Create significant bits chunk (convenience wrapper)
    
    Args:
        color_type: PNG color type
        *args: Depends on color_type:
            COLOR_TYPE_GRAYSCALE: gray_bits (int)
            COLOR_TYPE_RGB: red_bits, green_bits, blue_bits (int)
            COLOR_TYPE_INDEXED: palette_bits (int)
            COLOR_TYPE_GRAYSCALE_ALPHA: gray_bits, alpha_bits (int)
            COLOR_TYPE_RGBA: red_bits, green_bits, blue_bits, alpha_bits (int)
    
    Returns:
        sBIT chunk bytes
    '''
    if color_type == COLOR_TYPE_GRAYSCALE:
        if len(args) != 1:
            raise ValueError('grayscale requires 1 argument: gray_bits')
        return create_sBIT_for_grayscale(args[0])
    elif color_type == COLOR_TYPE_RGB:
        if len(args) != 3:
            raise ValueError('RGB requires 3 arguments: red_bits, green_bits, blue_bits')
        return create_sBIT_for_rgb(args[0], args[1], args[2])
    elif color_type == COLOR_TYPE_INDEXED:
        if len(args) != 1:
            raise ValueError('indexed requires 1 argument: palette_bits')
        return create_sBIT_for_indexed(args[0])
    elif color_type == COLOR_TYPE_GRAYSCALE_ALPHA:
        if len(args) != 2:
            raise ValueError('grayscale+alpha requires 2 arguments: gray_bits, alpha_bits')
        return create_sBIT_for_grayscale_alpha(args[0], args[1])
    elif color_type == COLOR_TYPE_RGBA:
        if len(args) != 4:
            raise ValueError('RGBA requires 4 arguments: red_bits, green_bits, blue_bits, alpha_bits')
        return create_sBIT_for_rgba(args[0], args[1], args[2], args[3])
    else:
        raise ValueError(f'unsupported color type for sBIT: {color_type}')

# ==================== Preset Values ====================

def create_common_gamma_values() -> dict:
    '''Return common gamma values'''
    return {
        'srgb': 0.45455,      # 1/2.2 ≈ 0.45455
        'gamma_1_8': 0.55556, # 1/1.8 ≈ 0.55556
        'gamma_2_0': 0.50000, # 1/2.0 = 0.50000
        'gamma_2_2': 0.45455, # 1/2.2 ≈ 0.45455
        'gamma_2_4': 0.41667, # 1/2.4 ≈ 0.41667
    }

def create_common_chromaticities() -> dict:
    '''Return common chromaticity values'''
    return {
        'srgb': {
            'white_point_x': 0.3127,
            'white_point_y': 0.3290,
            'red_x': 0.6400,
            'red_y': 0.3300,
            'green_x': 0.3000,
            'green_y': 0.6000,
            'blue_x': 0.1500,
            'blue_y': 0.0600,
        },
        'adobe_rgb_1998': {
            'white_point_x': 0.3127,
            'white_point_y': 0.3290,
            'red_x': 0.6400,
            'red_y': 0.3300,
            'green_x': 0.2100,
            'green_y': 0.7100,
            'blue_x': 0.1500,
            'blue_y': 0.0600,
        },
        'display_p3': {
            'white_point_x': 0.3127,
            'white_point_y': 0.3290,
            'red_x': 0.6800,
            'red_y': 0.3200,
            'green_x': 0.2650,
            'green_y': 0.6900,
            'blue_x': 0.1500,
            'blue_y': 0.0600,
        },
    }

# ==================== Adam7 Interlacing ====================

def get_adam7_passes(width: int, height: int) -> List[List[Tuple[int, int]]]:
    '''
    Calculate Adam7 interlacing passes
    
    Args:
        width: Image width
        height: Image height
    
    Returns:
        List of 7 lists, each containing (row, col) coordinates
    '''
    passes_params = [
        (0, 0, 8, 8),  # Pass 1
        (0, 4, 8, 8),  # Pass 2
        (4, 0, 8, 4),  # Pass 3
        (4, 2, 8, 4),  # Pass 4
        (2, 0, 4, 2),  # Pass 5
        (2, 1, 4, 2),  # Pass 6
        (1, 0, 2, 1),  # Pass 7
    ]
    
    pixels_by_pass = [[] for _ in range(7)]
    
    for pass_num, (y_start, x_start, y_step, x_step) in enumerate(passes_params):
        y = y_start
        while y < height:
            x = x_start
            while x < width:
                pixels_by_pass[pass_num].append((y, x))
                x += x_step
            y += y_step
    
    return pixels_by_pass

def _create_interlaced_high_bit_depth(image_data: bytes, width: int, height: int,
                                     color_type: int, bit_depth: int) -> bytes:
    '''Create interlaced data for 8/16-bit depth'''
    bytes_per_channel = 1 if bit_depth == 8 else 2
    
    # Calculate bytes per pixel based on color type
    if color_type == COLOR_TYPE_GRAYSCALE:
        bytes_per_pixel = bytes_per_channel
    elif color_type == COLOR_TYPE_RGB:
        bytes_per_pixel = 3 * bytes_per_channel
    elif color_type == COLOR_TYPE_INDEXED:
        bytes_per_pixel = 1
    elif color_type == COLOR_TYPE_GRAYSCALE_ALPHA:
        bytes_per_pixel = 2 * bytes_per_channel
    elif color_type == COLOR_TYPE_RGBA:
        bytes_per_pixel = 4 * bytes_per_channel
    else:
        raise ValueError(f'invalid color type: {color_type}')
    
    row_stride = width * bytes_per_pixel
    pixels = []
    
    for y in range(height):
        row_start = y * row_stride
        row = []
        for x in range(width):
            pixel_start = row_start + x * bytes_per_pixel
            row.append(image_data[pixel_start:pixel_start + bytes_per_pixel])
        pixels.append(row)
    
    passes = get_adam7_passes(width, height)
    interlaced_data = bytearray()
    
    for pass_pixels in passes:
        if not pass_pixels:
            continue
        
        current_row = -1
        row_data = bytearray()
        
        for y, x in sorted(pass_pixels):
            if y != current_row:
                if current_row != -1:
                    interlaced_data.extend(row_data)
                    row_data = bytearray()
                interlaced_data.append(0)  # Filter byte
                current_row = y
            
            row_data.extend(pixels[y][x])
        
        if row_data:
            interlaced_data.extend(row_data)
    
    return bytes(interlaced_data)

def _create_interlaced_low_bit_depth(image_data: bytes, width: int, height: int,
                                    color_type: int, bit_depth: int) -> bytes:
    '''Create interlaced data for 1,2,4-bit depth'''
    pixels_per_byte = 8 // bit_depth
    mask = (1 << bit_depth) - 1
    
    # Unpack bytes to pixel values
    pixels = []
    for y in range(height):
        row_start = y * ((width + pixels_per_byte - 1) // pixels_per_byte)
        row = []
        
        for x in range(width):
            byte_index = row_start + x // pixels_per_byte
            if byte_index < len(image_data):
                byte = image_data[byte_index]
                shift = 8 - ((x % pixels_per_byte) + 1) * bit_depth
                row.append((byte >> shift) & mask)
            else:
                row.append(0)
        
        pixels.append(row)
    
    passes = get_adam7_passes(width, height)
    interlaced_data = bytearray()
    
    for pass_pixels in passes:
        if not pass_pixels:
            continue
        
        current_row = -1
        current_byte = 0
        bits_in_current_byte = 0
        
        for y, x in sorted(pass_pixels):
            if y != current_row:
                if current_row != -1:
                    if bits_in_current_byte > 0:
                        interlaced_data.append(current_byte)
                        current_byte = 0
                        bits_in_current_byte = 0
                interlaced_data.append(0)  # Filter byte
                current_row = y
            
            pixel_value = pixels[y][x]
            current_byte = (current_byte << bit_depth) | pixel_value
            bits_in_current_byte += bit_depth
            
            if bits_in_current_byte == 8:
                interlaced_data.append(current_byte)
                current_byte = 0
                bits_in_current_byte = 0
        
        if bits_in_current_byte > 0:
            current_byte <<= (8 - bits_in_current_byte)
            interlaced_data.append(current_byte)
    
    return bytes(interlaced_data)

def create_interlaced_data(image_data: bytes, width: int, height: int,
                          color_type: int, bit_depth: int = 8) -> bytes:
    '''
    Convert image data to Adam7 interlaced format
    
    Args:
        image_data: Raw image data
        width: Image width
        height: Image height
        color_type: Color type
        bit_depth: Bit depth
    
    Returns:
        Interlaced data bytes with filter bytes
    '''
    if bit_depth < 8:
        return _create_interlaced_low_bit_depth(image_data, width, height,
                                               color_type, bit_depth)
    else:
        return _create_interlaced_high_bit_depth(image_data, width, height,
                                                color_type, bit_depth)

# ==================== Helper Functions ====================

def pack_pixels_to_bytes(pixel_values: List[int], bit_depth: int) -> bytes:
    '''
    Pack pixel values into bytes (for low bit depths)
    
    Args:
        pixel_values: List of pixel values
        bit_depth: Bit depth (1, 2, 4, 8)
    
    Returns:
        Packed bytes
    '''
    if bit_depth == 8:
        return bytes(pixel_values)
    
    pixels_per_byte = 8 // bit_depth
    mask = (1 << bit_depth) - 1
    result = bytearray()
    current_byte = 0
    bits_filled = 0
    
    for pixel in pixel_values:
        current_byte = (current_byte << bit_depth) | (pixel & mask)
        bits_filled += bit_depth
        
        if bits_filled == 8:
            result.append(current_byte)
            current_byte = 0
            bits_filled = 0
    
    if bits_filled > 0:
        current_byte <<= (8 - bits_filled)
        result.append(current_byte)
    
    return bytes(result)

# ==================== PNG Creation Functions ====================

def create_simple_png(width: int, height: int,
                     rgb_data: bytes,
                     interlace: bool = False) -> bytes:
    '''
    Create a simple RGB PNG file
    
    Args:
        width: Image width
        height: Image height
        rgb_data: RGB data (width * height * 3 bytes)
        interlace: Whether to use interlacing
    
    Returns:
        Complete PNG file as bytes
    '''
    expected_length = width * height * 3
    if len(rgb_data) != expected_length:
        raise ValueError(f'expected {expected_length} bytes, got {len(rgb_data)}')
    
    ihdr = create_IHDR(width, height,
                      bit_depth=8,
                      color_type=COLOR_TYPE_RGB,
                      interlace_method=1 if interlace else 0)
    
    if interlace:
        image_data = create_interlaced_data(rgb_data, width, height,
                                           COLOR_TYPE_RGB, 8)
    else:
        image_data = bytearray()
        row_stride = width * 3
        
        for y in range(height):
            row_start = y * row_stride
            image_data.append(0)  # Filter byte
            image_data.extend(rgb_data[row_start:row_start + row_stride])
    
    compressed_data = zlib.compress(bytes(image_data))
    idat = create_png_chunk(b'IDAT', compressed_data)
    iend = create_IEND()
    
    return PNG_SIGNATURE + ihdr + idat + iend

def create_grayscale_png(width: int, height: int,
                        grayscale_data: bytes,
                        bit_depth: int = 8,
                        interlace: bool = False) -> bytes:
    '''
    Create a grayscale PNG file
    
    Args:
        width: Image width
        height: Image height
        grayscale_data: Grayscale data
        bit_depth: Bit depth (8 or 16)
        interlace: Whether to use interlacing
    
    Returns:
        Complete PNG file as bytes
    '''
    if bit_depth not in (8, 16):
        raise ValueError('grayscale PNG supports only 8 or 16-bit depth')
    
    bytes_per_pixel = 1 if bit_depth == 8 else 2
    expected_length = width * height * bytes_per_pixel
    
    if len(grayscale_data) != expected_length:
        raise ValueError(f'expected {expected_length} bytes, got {len(grayscale_data)}')
    
    ihdr = create_IHDR(width, height,
                      bit_depth=bit_depth,
                      color_type=COLOR_TYPE_GRAYSCALE,
                      interlace_method=1 if interlace else 0)
    
    if interlace:
        image_data = create_interlaced_data(grayscale_data, width, height,
                                           COLOR_TYPE_GRAYSCALE, bit_depth)
    else:
        image_data = bytearray()
        row_stride = width * bytes_per_pixel
        
        for y in range(height):
            row_start = y * row_stride
            image_data.append(0)  # Filter byte
            image_data.extend(grayscale_data[row_start:row_start + row_stride])
    
    compressed_data = zlib.compress(bytes(image_data))
    idat = create_png_chunk(b'IDAT', compressed_data)
    iend = create_IEND()
    
    return PNG_SIGNATURE + ihdr + idat + iend

def create_indexed_png(width: int, height: int,
                      indexed_data: bytes,
                      palette: List[Tuple[int, int, int]],
                      bit_depth: int = 8,
                      interlace: bool = False) -> bytes:
    '''
    Create indexed color PNG with palette
    
    Args:
        width: Image width
        height: Image height
        indexed_data: Indexed color data
        palette: Color palette [(r,g,b), ...]
        bit_depth: Bit depth (1, 2, 4, 8)
        interlace: Whether to use interlacing
    
    Returns:
        Complete PNG file as bytes
    '''
    if bit_depth not in (1, 2, 4, 8):
        raise ValueError('indexed color supports only 1, 2, 4, or 8-bit depth')
    
    # For bit depths < 8, data should already be packed
    if bit_depth == 8:
        expected_length = width * height
    else:
        pixels_per_byte = 8 // bit_depth
        expected_length = (width * height + pixels_per_byte - 1) // pixels_per_byte
    
    if len(indexed_data) != expected_length:
        raise ValueError(f'expected {expected_length} bytes, got {len(indexed_data)}')
    
    ihdr = create_IHDR(width, height,
                      bit_depth=bit_depth,
                      color_type=COLOR_TYPE_INDEXED,
                      interlace_method=1 if interlace else 0)
    
    plte = create_PLTE(palette)
    
    if interlace:
        image_data = create_interlaced_data(indexed_data, width, height,
                                           COLOR_TYPE_INDEXED, bit_depth)
    else:
        image_data = bytearray()
        
        if bit_depth < 8:
            bytes_per_row = (width * bit_depth + 7) // 8
            for y in range(height):
                row_start = y * bytes_per_row
                image_data.append(0)  # Filter byte
                image_data.extend(indexed_data[row_start:row_start + bytes_per_row])
        else:
            row_stride = width
            for y in range(height):
                row_start = y * row_stride
                image_data.append(0)  # Filter byte
                image_data.extend(indexed_data[row_start:row_start + row_stride])
    
    compressed_data = zlib.compress(bytes(image_data))
    idat = create_png_chunk(b'IDAT', compressed_data)
    iend = create_IEND()
    
    return PNG_SIGNATURE + ihdr + plte + idat + iend

def create_rgba_png(width: int, height: int,
                   rgba_data: bytes,
                   bit_depth: int = 8,
                   interlace: bool = False) -> bytes:
    '''
    Create RGBA PNG with transparency
    
    Args:
        width: Image width
        height: Image height
        rgba_data: RGBA data (width * height * 4 bytes)
        bit_depth: Bit depth (8 or 16)
        interlace: Whether to use interlacing
    
    Returns:
        Complete PNG file as bytes
    '''
    if bit_depth not in (8, 16):
        raise ValueError('RGBA PNG supports only 8 or 16-bit depth')
    
    bytes_per_pixel = 4 if bit_depth == 8 else 8
    expected_length = width * height * bytes_per_pixel
    
    if len(rgba_data) != expected_length:
        raise ValueError(f'expected {expected_length} bytes, got {len(rgba_data)}')
    
    ihdr = create_IHDR(width, height,
                      bit_depth=bit_depth,
                      color_type=COLOR_TYPE_RGBA,
                      interlace_method=1 if interlace else 0)
    
    if interlace:
        image_data = create_interlaced_data(rgba_data, width, height,
                                           COLOR_TYPE_RGBA, bit_depth)
    else:
        image_data = bytearray()
        row_stride = width * bytes_per_pixel
        
        for y in range(height):
            row_start = y * row_stride
            image_data.append(0)  # Filter byte
            image_data.extend(rgba_data[row_start:row_start + row_stride])
    
    compressed_data = zlib.compress(bytes(image_data))
    idat = create_png_chunk(b'IDAT', compressed_data)
    iend = create_IEND()
    
    return PNG_SIGNATURE + ihdr + idat + iend

# ==================== Filter Functions ====================

def apply_filter_none(scanline: bytes) -> bytes:
    '''Filter type 0: None'''
    return scanline

def apply_filter_sub(scanline: bytes, bytes_per_pixel: int) -> bytes:
    '''Filter type 1: Sub (difference from left pixel)'''
    filtered = bytearray(len(scanline))
    for i in range(len(scanline)):
        if i < bytes_per_pixel:
            filtered[i] = scanline[i]
        else:
            filtered[i] = (scanline[i] - scanline[i - bytes_per_pixel]) & 0xFF
    return bytes(filtered)

def apply_filter_up(scanline: bytes, previous_scanline: bytes) -> bytes:
    '''Filter type 2: Up (difference from above pixel)'''
    filtered = bytearray(len(scanline))
    for i in range(len(scanline)):
        filtered[i] = (scanline[i] - previous_scanline[i]) & 0xFF
    return bytes(filtered)

def apply_filter_average(scanline: bytes, previous_scanline: bytes, bytes_per_pixel: int) -> bytes:
    '''Filter type 3: Average (average of left and above pixels)'''
    filtered = bytearray(len(scanline))
    for i in range(len(scanline)):
        left = scanline[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
        up = previous_scanline[i]
        avg = (left + up) // 2
        filtered[i] = (scanline[i] - avg) & 0xFF
    return bytes(filtered)

def apply_filter_paeth(scanline: bytes, previous_scanline: bytes, bytes_per_pixel: int) -> bytes:
    '''Filter type 4: Paeth predictor'''
    filtered = bytearray(len(scanline))
    
    for i in range(len(scanline)):
        a = scanline[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
        b = previous_scanline[i]
        c = previous_scanline[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
        
        # Paeth predictor
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        
        if pa <= pb and pa <= pc:
            predictor = a
        elif pb <= pc:
            predictor = b
        else:
            predictor = c
        
        filtered[i] = (scanline[i] - predictor) & 0xFF
    
    return bytes(filtered)

def calculate_abs_sum(data: bytes) -> int:
    '''Calculate sum of absolute values (for filter selection)'''
    return sum(byte if byte < 128 else 256 - byte for byte in data)

def select_best_filter(scanline: bytes, previous_scanline: Optional[bytes], bytes_per_pixel: int) -> Tuple[int, bytes]:
    '''
    Select the best filter for a scanline
    
    Args:
        scanline: Current scanline data
        previous_scanline: Previous scanline data (None for first row)
        bytes_per_pixel: Bytes per pixel
    
    Returns:
        Tuple of (filter_type, filtered_data)
    '''
    filters = []
    
    # Filter 0: None (always available)
    filtered_0 = apply_filter_none(scanline)
    filters.append((0, filtered_0, calculate_abs_sum(filtered_0)))
    
    # Filter 1: Sub (always available if bytes_per_pixel > 0)
    if bytes_per_pixel > 0:
        filtered_1 = apply_filter_sub(scanline, bytes_per_pixel)
        filters.append((1, filtered_1, calculate_abs_sum(filtered_1)))
    
    # Filters 2, 3, 4 require a previous scanline
    if previous_scanline is not None:
        # Filter 2: Up
        filtered_2 = apply_filter_up(scanline, previous_scanline)
        filters.append((2, filtered_2, calculate_abs_sum(filtered_2)))
        
        # Filter 3: Average (needs bytes_per_pixel)
        if bytes_per_pixel > 0:
            filtered_3 = apply_filter_average(scanline, previous_scanline, bytes_per_pixel)
            filters.append((3, filtered_3, calculate_abs_sum(filtered_3)))
        
        # Filter 4: Paeth (needs bytes_per_pixel)
        if bytes_per_pixel > 0:
            filtered_4 = apply_filter_paeth(scanline, previous_scanline, bytes_per_pixel)
            filters.append((4, filtered_4, calculate_abs_sum(filtered_4)))
    
    # Select filter with minimum absolute sum
    best_filter = min(filters, key=lambda x: x[2])
    return best_filter[0], best_filter[1]

# ==================== Modified PNG Creation with Optimal Filtering ====================

def create_png(width: int, height: int,
               image_data: bytes,
               color_type: int = COLOR_TYPE_RGB,
               bit_depth: int = 8,
               interlace: bool = False,
               palette: Optional[List[Tuple[int, int, int]]] = None,
               auxiliary_chunks: Optional[Dict[str, tuple]] = None,
               use_optimal_filter: bool = True) -> bytes:
    '''
    Create a complete PNG file with support for auxiliary chunks
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        image_data: Raw image data bytes
        color_type: PNG color type (0, 2, 3, 4, 6)
        bit_depth: Bit depth (1, 2, 4, 8, 16)
        interlace: Whether to use Adam7 interlacing
        palette: Color palette for indexed color (list of RGB tuples)
        auxiliary_chunks: Dictionary of auxiliary chunks to include
                         Key: Chunk type (e.g., 'tRNS', 'gAMA', 'tEXt')
                         Value: Tuple of arguments for the corresponding creation function
                             or 'now' for tIME (creates current time)
        use_optimal_filter: Whether to use optimal filter selection (True) or always use filter 0 (False)
    
    Returns:
        Complete PNG file as bytes
    
    Example:
        # Create PNG with transparency and text
        png_data = create_png(
            width=64,
            height=64,
            image_data=rgb_data,
            auxiliary_chunks={
                'tRNS': ([255],),  # Single transparent color
                'tEXt': ('Author', 'John Doe'),
                'tIME': (2024, 1, 15, 10, 30, 0)  # or 'now' for current time
            }
        )
    '''
    # ==================== Validation ====================
    
    if width <= 0 or height <= 0:
        raise ValueError("'width' and 'height' must be positive integers")
    
    if auxiliary_chunks is None:
        auxiliary_chunks = {}
    
    # ==================== Create IHDR ====================
    
    ihdr_chunk = create_IHDR(width, height,
                            bit_depth=bit_depth,
                            color_type=color_type,
                            interlace_method=1 if interlace else 0)
    
    # ==================== Create PLTE if needed ====================
    
    chunks = [PNG_SIGNATURE, ihdr_chunk]
    
    if color_type == COLOR_TYPE_INDEXED:
        if palette is None:
            raise ValueError("'palette' is required for indexed color images")
        plte_chunk = create_PLTE(palette)
        chunks.append(plte_chunk)
    elif palette is not None:
        warnings.warn("'palette' is ignored for non-indexed color images", UserWarning)
    
    # ==================== Process auxiliary chunks ====================
    
    # Process each auxiliary chunk
    for chunk_type, args in auxiliary_chunks.items():
        try:
            if chunk_type == 'tRNS':
                if isinstance(args[0], list):
                    chunk = create_tRNS(*args)
                else:
                    chunk = create_tRNS([args[0]])
            
            elif chunk_type == 'gAMA':
                chunk = create_gAMA(*args)
            
            elif chunk_type == 'cHRM':
                chunk = create_cHRM(*args)
            
            elif chunk_type == 'sRGB':
                chunk = create_sRGB(*args)
            
            elif chunk_type == 'iCCP':
                chunk = create_iCCP(*args)
            
            elif chunk_type == 'tEXt':
                chunk = create_tEXt(*args)
            
            elif chunk_type == 'zTXt':
                chunk = create_zTXt(*args)
            
            elif chunk_type == 'iTXt':
                chunk = create_iTXt(*args)
            
            elif chunk_type == 'bKGD':
                chunk = create_bKGD(color_type, *args)
            
            elif chunk_type == 'pHYs':
                chunk = create_pHYs(*args)
            
            elif chunk_type == 'sBIT':
                chunk = create_sBIT(color_type, *args)
            
            elif chunk_type == 'tIME':
                if args == 'now' or args == ('now',):
                    chunk = create_tIME_now()
                else:
                    chunk = create_tIME(*args)
            
            else:
                warnings.warn(f'unknown auxiliary chunk type: {chunk_type}', UserWarning)
                continue
            
            chunks.append(chunk)
            
        except Exception as e:
            warnings.warn(f'failed to create {chunk_type} chunk: {e}', UserWarning)
    
    # ==================== Prepare image data ====================
    
    if interlace:
        # Use interlaced data preparation
        prepared_data = create_interlaced_data(image_data, width, height,
                                              color_type, bit_depth)
    else:
        # Prepare non-interlaced data
        prepared_data = bytearray()
        
        # Calculate bytes per pixel and row stride
        if bit_depth == 8:
            bytes_per_channel = 1
        elif bit_depth == 16:
            bytes_per_channel = 2
        else:
            bytes_per_channel = 1  # For packed bits
        
        # Calculate bytes per pixel based on color type
        if color_type == COLOR_TYPE_GRAYSCALE:
            bytes_per_pixel = bytes_per_channel
        elif color_type == COLOR_TYPE_RGB:
            bytes_per_pixel = 3 * bytes_per_channel
        elif color_type == COLOR_TYPE_INDEXED:
            bytes_per_pixel = 1
        elif color_type == COLOR_TYPE_GRAYSCALE_ALPHA:
            bytes_per_pixel = 2 * bytes_per_channel
        elif color_type == COLOR_TYPE_RGBA:
            bytes_per_pixel = 4 * bytes_per_channel
        else:
            raise ValueError(f'invalid color type: {color_type}')
        
        row_stride = width * bytes_per_pixel
        
        # For bit depths < 8, data is already packed
        if bit_depth < 8:
            if color_type not in (COLOR_TYPE_GRAYSCALE, COLOR_TYPE_INDEXED):
                raise ValueError(f'bit depth {bit_depth} is only supported for grayscale or indexed color')
            
            bytes_per_row = (width * bit_depth + 7) // 8
            total_bytes = bytes_per_row * height
            
            if len(image_data) != total_bytes:
                raise ValueError(
                    f'expected {total_bytes} bytes for {bit_depth}-bit '
                    f'{"grayscale" if color_type == COLOR_TYPE_GRAYSCALE else "indexed"} data, '
                    f'got {len(image_data)}'
                )
            
            for y in range(height):
                row_start = y * bytes_per_row
                prepared_data.append(0)  # Filter byte 0
                prepared_data.extend(image_data[row_start:row_start + bytes_per_row])
        else:
            # For 8/16 bit depths
            expected_length = height * row_stride
            
            if len(image_data) != expected_length:
                raise ValueError(
                    f'expected {expected_length} bytes, got {len(image_data)}'
                )
            
            if use_optimal_filter:
                # Use optimal filter
                previous_row_data = None
                
                for y in range(height):
                    row_start = y * row_stride
                    row_data = image_data[row_start:row_start + row_stride]
                    
                    # For the first row, previous_row_data is None
                    filter_type, filtered_row = select_best_filter(
                        row_data, previous_row_data, bytes_per_pixel
                    )
                    
                    prepared_data.append(filter_type)
                    prepared_data.extend(filtered_row)
                    
                    # Update the data of the previous row for the filter selection of the next row
                    previous_row_data = row_data
            else:
                # Always use filter 0
                for y in range(height):
                    row_start = y * row_stride
                    prepared_data.append(0)  # Filter byte 0
                    prepared_data.extend(image_data[row_start:row_start + row_stride])
    
    # ==================== Compress and create IDAT ====================
    
    compressed_data = zlib.compress(bytes(prepared_data))
    idat_chunk = create_png_chunk(b'IDAT', compressed_data)
    chunks.append(idat_chunk)
    
    # ==================== Create IEND ====================
    
    iend_chunk = create_IEND()
    chunks.append(iend_chunk)
    
    # ==================== Combine all chunks ====================
    
    return b''.join(chunks)

# ==================== Convenience Functions ====================

def create_png_from_rgb(width: int, height: int,
                        rgb_data: bytes,
                        **kwargs) -> bytes:
    '''
    Convenience function to create RGB PNG
    
    Args:
        width: Image width
        height: Image height
        rgb_data: RGB data (width * height * 3 bytes)
        **kwargs: Additional arguments for create_png()
    
    Returns:
        Complete PNG file as bytes
    '''
    return create_png(width, height, rgb_data,
                     color_type=COLOR_TYPE_RGB,
                     bit_depth=8,
                     **kwargs)

def create_png_from_grayscale(width: int, height: int,
                             gray_data: bytes,
                             bit_depth: int = 8,
                             **kwargs) -> bytes:
    '''
    Convenience function to create grayscale PNG
    
    Args:
        width: Image width
        height: Image height
        gray_data: Grayscale data
        bit_depth: Bit depth (8 or 16)
        **kwargs: Additional arguments for create_png()
    
    Returns:
        Complete PNG file as bytes
    '''
    return create_png(width, height, gray_data,
                     color_type=COLOR_TYPE_GRAYSCALE,
                     bit_depth=bit_depth,
                     **kwargs)

def create_png_from_rgba(width: int, height: int,
                        rgba_data: bytes,
                        bit_depth: int = 8,
                        **kwargs) -> bytes:
    '''
    Convenience function to create RGBA PNG
    
    Args:
        width: Image width
        height: Image height
        rgba_data: RGBA data (width * height * 4 bytes for 8-bit)
        bit_depth: Bit depth (8 or 16)
        **kwargs: Additional arguments for create_png()
    
    Returns:
        Complete PNG file as bytes
    '''
    return create_png(width, height, rgba_data,
                     color_type=COLOR_TYPE_RGBA,
                     bit_depth=bit_depth,
                     **kwargs)

def create_png_from_indexed(width: int, height: int,
                           indexed_data: bytes,
                           palette: List[Tuple[int, int, int]],
                           bit_depth: int = 8,
                           **kwargs) -> bytes:
    '''
    Convenience function to create indexed PNG
    
    Args:
        width: Image width
        height: Image height
        indexed_data: Indexed color data
        palette: Color palette
        bit_depth: Bit depth (1, 2, 4, 8)
        **kwargs: Additional arguments for create_png()
    
    Returns:
        Complete PNG file as bytes
    '''
    return create_png(width, height, indexed_data,
                     color_type=COLOR_TYPE_INDEXED,
                     bit_depth=bit_depth,
                     palette=palette,
                     **kwargs)

# ==================== Test Image Creation Functions ====================

def create_test_rgb_image() -> Tuple[int, int, bytes]:
    '''Create a simple test RGB image (64x64 gradient)'''
    width, height = 64, 64
    data = bytearray()
    
    for y in range(height):
        for x in range(width):
            r = int(x / width * 255)
            g = int(y / height * 255)
            b = 128
            data.extend([r, g, b])
    
    return width, height, bytes(data)

def test_enlarge_image_comprehensive():
    '''Comprehensive test for enlarge_image function'''
    print('Testing enlarge_image function with various formats...')
    
    # Test 1: 8-bit grayscale
    print('\nTest 1: 8-bit grayscale 2x2 -> 4x4')
    width, height = 2, 2
    gray_data = bytes([0, 255, 128, 64])
    scaled = enlarge_image(width, height, gray_data, 2, COLOR_TYPE_GRAYSCALE, 8)
    expected_size = 4 * 4 * 1  # 4x4 pixels, 1 byte per pixel
    assert len(scaled) == expected_size, f'Expected {expected_size} bytes, got {len(scaled)}'
    print('✓ 8-bit grayscale test passed')
    
    # Test 2: 4-bit indexed color
    print('\nTest 2: 4-bit indexed 4x4 -> 8x8')
    width, height = 4, 4
    # Create packed 4-bit data (2 pixels per byte)
    # Pixel values: 0-15 for 4-bit
    packed_data = bytes([
        0x01, 0x23,  # Row 1: pixels 0,1,2,3
        0x45, 0x67,  # Row 2: pixels 4,5,6,7
        0x89, 0xAB,  # Row 3: pixels 8,9,10,11
        0xCD, 0xEF   # Row 4: pixels 12,13,14,15
    ])
    scaled = enlarge_image(width, height, packed_data, 2, COLOR_TYPE_INDEXED, 4)
    # After 2x scaling: 8x8 pixels, packed as 4-bit (2 pixels per byte)
    expected_bytes = (8 * 8 + 1) // 2  # 64 pixels / 2 pixels per byte = 32 bytes
    assert len(scaled) == expected_bytes, f'Expected {expected_bytes} bytes, got {len(scaled)}'
    print('✓ 4-bit indexed test passed')
    
    # Test 3: 2-bit grayscale
    print('\nTest 3: 2-bit grayscale 4x4 -> 8x8')
    # 2-bit grayscale: 4 levels (0,1,2,3), 4 pixels per byte
    packed_2bit = bytes([
        0x00, 0x55, 0xAA, 0xFF,  # Various patterns
    ])
    scaled = enlarge_image(4, 4, packed_2bit, 2, COLOR_TYPE_GRAYSCALE, 2)
    expected_bytes = (8 * 8 + 3) // 4  # 64 pixels / 4 pixels per byte = 16 bytes
    assert len(scaled) == expected_bytes, f'Expected {expected_bytes} bytes, got {len(scaled)}'
    print('✓ 2-bit grayscale test passed')
    
    # Test 4: 1-bit indexed (monochrome)
    print('\nTest 4: 1-bit indexed 8x8 -> 16x16')
    width, height = 8, 8
    # Create checkerboard pattern: 8 pixels per byte
    checkerboard = bytes([
        0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x55, 0xAA, 0x55  # 8 rows
    ])
    scaled = enlarge_image(width, height, checkerboard, 2, COLOR_TYPE_INDEXED, 1)
    expected_bytes = (16 * 16 + 7) // 8  # 256 pixels / 8 pixels per byte = 32 bytes
    assert len(scaled) == expected_bytes, f'Expected {expected_bytes} bytes, got {len(scaled)}'
    print('✓ 1-bit indexed test passed')
    
    # Test 5: 8-bit RGB
    print('\nTest 5: 8-bit RGB 3x2 -> 6x4')
    width, height = 3, 2
    rgb_data = bytes([
        255, 0, 0,   0, 255, 0,   0, 0, 255,  # Row 1: Red, Green, Blue
        255, 255, 0, 255, 0, 255, 0, 255, 255  # Row 2: Yellow, Magenta, Cyan
    ])
    scaled = enlarge_image(width, height, rgb_data, 2, COLOR_TYPE_RGB, 8)
    expected_size = 6 * 4 * 3  # 6x4 pixels, 3 bytes per pixel
    assert len(scaled) == expected_size, f'Expected {expected_size} bytes, got {len(scaled)}'
    print('✓ 8-bit RGB test passed')
    
    # Test 6: 8-bit RGBA
    print('\nTest 6: 8-bit RGBA 2x2 -> 4x4')
    width, height = 2, 2
    rgba_data = bytes([
        255, 0, 0, 255,      # Red
        0, 255, 0, 128,      # Green with 50% alpha
        0, 0, 255, 64,       # Blue with 25% alpha
        255, 255, 0, 192     # Yellow with 75% alpha
    ])
    scaled = enlarge_image(width, height, rgba_data, 2, COLOR_TYPE_RGBA, 8)
    expected_size = 4 * 4 * 4  # 4x4 pixels, 4 bytes per pixel
    assert len(scaled) == expected_size, f'Expected {expected_size} bytes, got {len(scaled)}'
    print('✓ 8-bit RGBA test passed')
    
    # Test 7: 16-bit grayscale
    print('\nTest 7: 16-bit grayscale 2x2 -> 4x4')
    width, height = 2, 2
    gray16_data = bytes([
        0, 0,      # 0
        255, 255,  # 65535
        128, 0,    # 32768
        64, 0      # 16384
    ])
    scaled = enlarge_image(width, height, gray16_data, 2, COLOR_TYPE_GRAYSCALE, 16)
    expected_size = 4 * 4 * 2  # 4x4 pixels, 2 bytes per pixel
    assert len(scaled) == expected_size, f'Expected {expected_size} bytes, got {len(scaled)}'
    print('✓ 16-bit grayscale test passed')
    
    print('\n' + '=' * 50)
    print('All tests passed successfully!')
    print('=' * 50)

# ==================== Example Usage ====================

if __name__ == '__main__':
    # Run comprehensive tests first
    test_enlarge_image_comprehensive()
    
    print('\n' + '=' * 50 + '\nExample Usage:\n' + '=' * 50)
    
    # Example 1: Simple RGB PNG with metadata
    print('\nCreating RGB PNG with metadata...')
    width, height, rgb_data = create_test_rgb_image()
    
    png_data = create_png(
        width=width,
        height=height,
        image_data=rgb_data,
        color_type=COLOR_TYPE_RGB,
        auxiliary_chunks={
            'tEXt': ('Author', 'PNG Utils Library'),
            'zTXt': ('Description', 'Test RGB image'),
            'tIME': 'now',  # Use current time
            'gAMA': (0.45455,),  # Gamma 2.2
            'pHYs': (72, 72, 1),  # 72 DPI
        },
        use_optimal_filter=False
    )
    
    with open('test_rgb_meta.png', 'wb') as f:
        f.write(png_data)
    print(f'RGB PNG with metadata created: {len(png_data)} bytes')
    
    # Example 2: RGBA PNG with transparency hint and the best filter
    print('\nCreating RGBA PNG...')
    width, height = 64, 64
    rgba_data = bytearray()
    for y in range(height):
        for x in range(width):
            r = int(x / width * 255)
            g = int(y / height * 255)
            b = 128
            a = int((x + y) / (width + height) * 255)  # Alpha gradient
            rgba_data.extend([r, g, b, a])
    
    png_data = create_png_from_rgba(
        width=width,
        height=height,
        rgba_data=bytes(rgba_data),
        auxiliary_chunks={
            'tEXt': ('Software', 'png_utils.py'),
            'sBIT': (8, 8, 8, 8),  # All channels use 8 bits
        }
    )
    
    with open('test_rgba.png', 'wb') as f:
        f.write(png_data)
    print(f'RGBA PNG created: {len(png_data)} bytes')
    
    # Example 3: Indexed PNG with palette and transparency
    print('\nCreating indexed PNG...')
    width, height = 32, 32
    palette = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (255, 255, 0),  # Yellow
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Cyan
    ]
    
    # Create simple indexed data
    indexed_data = bytearray()
    for y in range(height):
        for x in range(width):
            color_idx = (x // 8 + y // 8) % len(palette)
            indexed_data.append(color_idx)
    
    png_data = create_png_from_indexed(
        width=width,
        height=height,
        indexed_data=bytes(indexed_data),
        palette=palette,
        bit_depth=8,
        auxiliary_chunks={
            'tRNS': ([255, 0, 0, 0, 0, 0],),  # Make first color (red) transparent
            'tEXt': ('Palette', '6-color test palette'),
        },
        use_optimal_filter=False
    )
    
    with open('test_indexed.png', 'wb') as f:
        f.write(png_data)
    print(f'Indexed PNG created: {len(png_data)} bytes')
    
    print('\n' + '=' * 50)
    print('All test PNG files saved successfully!')
