import svgwrite
from dataclasses import dataclass, astuple
from typing import List, Tuple, Union
import math
from reedsolo import RSCodec, ReedSolomonError


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Dim:
    width: float
    height: float


@dataclass
class Rect:
    point: Point
    dim: Dim


@dataclass
class Pad:
    left: float
    right: float
    top: float
    bottom: float


@dataclass
class Size:
    rows: int
    cols: int


@dataclass
class Specification:
    bits: int
    size: Size
    white_frame_pad: Pad
    black_background_pad: Pad
    white_strip_height: float
    row_inset: float
    triangle_dim: Dim


# Color constants
BLACK = "#000000"
WHITE = "#FFFFFF"

FOUR_COLOR_MAP = [
    "#000000",  # black
    "#FFFF45",  # yellow
    "#12FF0E",  # green
    "#FF1400",  # red
]

EIGHT_COLOR_MAP = [
    "#000000",  # black
    "#FAFD28",  # yellow
    "#1CEC12",  # green
    "#DF0203",  # red
    "#FAFAFA",  # white
    "#1EF6EE",  # cyan
    "#F38BED",  # pink
    "#1833DE",  # blue
]


def draw_triangle(dwg, direction, fill, strip_height, triangle_dim, corner):
    stroke_width = 2
    if direction == "up":
        path = (
            f"M {corner.x + triangle_dim.width/2} {corner.y + strip_height} "
            f"l {triangle_dim.width/2} {triangle_dim.height} "
            f"l 0 {strip_height - stroke_width} "
            f"l {-triangle_dim.width} 0 "
            f"l 0 {-strip_height + stroke_width} "
            "z"
        )
    else:  # down
        path = (
            f"M {corner.x} {corner.y + stroke_width} "
            f"l {triangle_dim.width} 0 "
            f"l 0 {strip_height - stroke_width} "
            f"l {-triangle_dim.width/2} {triangle_dim.height} "
            f"l {-triangle_dim.width/2} {-triangle_dim.height} "
            "z"
        )
    dwg.add(dwg.path(d=path, fill=fill, stroke=WHITE, stroke_width=stroke_width))


def draw_rect(dwg, fill, rect):
    dwg.add(
        dwg.rect(
            insert=(rect.point.x, rect.point.y),
            size=(rect.dim.width, rect.dim.height),
            fill=fill,
        )
    )


def draw_frame(dwg, outside, inside):
    draw_rect(dwg, WHITE, outside)
    draw_rect(dwg, BLACK, inside)


def data_to_colors(bits, data):
    color_map = FOUR_COLOR_MAP if bits == 2 else EIGHT_COLOR_MAP
    mask = 3 if bits == 2 else 7
    shift = 2 if bits == 2 else 3
    colors = []
    for value in data:
        for i in range(8 // bits):
            index = (value >> (i * shift)) & mask
            colors.append(color_map[index])
    return colors


def colors_prefix(bits):
    colors = FOUR_COLOR_MAP if bits == 2 else EIGHT_COLOR_MAP
    return colors * 2


def get_row_spec(spec):
    row_dim = triangle_row_dim(spec)
    return {
        "width": row_dim.width,
        "inset": spec.row_inset,
        "strip_height": spec.white_strip_height,
        "space_height": spec.triangle_dim.height,
    }


def triangle_row_dim(spec):
    width = spec.triangle_dim.width * spec.size.cols / 2
    height = spec.triangle_dim.height + spec.white_strip_height
    return Dim(width, height)


def barcode_dim(spec):
    row_dim = triangle_row_dim(spec)
    width = (
        spec.white_frame_pad.left
        + spec.black_background_pad.left
        + spec.row_inset
        + row_dim.width
        + spec.row_inset
        + spec.black_background_pad.right
        + spec.white_frame_pad.right
    )
    height = (
        spec.white_frame_pad.top
        + spec.black_background_pad.top
        + (row_dim.height * (spec.size.rows + 1))
        + spec.white_frame_pad.bottom
    )
    return Dim(width, height)


def draw_triangles(dwg, spec, corner, data):
    row_spec = get_row_spec(spec)
    for i in range(spec.size.rows):
        for j in range(spec.size.cols):
            direction = "up" if j % 2 == 0 else "down"
            color = data[i * spec.size.cols + j]
            x = corner.x + (spec.size.cols - j - 1) * (spec.triangle_dim.width / 2)
            y = corner.y + (spec.size.rows - i - 1) * (
                row_spec["strip_height"] + row_spec["space_height"]
            )
            draw_triangle(
                dwg,
                direction,
                color,
                spec.white_strip_height,
                spec.triangle_dim,
                Point(x, y),
            )


def draw_strips(dwg, row_spec, corner, size):
    extra_pad = Pad(1.3, 1.8, 0, 0)
    strip_dim = Dim(
        row_spec["width"] + row_spec["inset"] * 2 + extra_pad.left + extra_pad.right,
        row_spec["strip_height"],
    )
    for row in range(size.rows + 1):
        y = corner.y + row * (row_spec["strip_height"] + row_spec["space_height"])
        rect = Rect(Point(corner.x - extra_pad.left, y), strip_dim)
        draw_rect(dwg, WHITE, rect)


def apply_reed_solomon(data, ecc_symbols):
    rs = RSCodec(ecc_symbols)
    return list(rs.encode(bytes(data)))


def calculate_dynamic_spec(data_length, max_width, max_height):
    base_spec = Specification(
        bits=3,
        size=Size(rows=12, cols=24),
        white_frame_pad=Pad(20.87, 20.87, 20.87, 20.87),
        black_background_pad=Pad(8.94, 8.94, 8.94, 8.94),
        white_strip_height=5.96,
        row_inset=5.96,
        triangle_dim=Dim(25.48, 20.87),
    )

    # Calculate required number of triangles
    required_triangles = math.ceil(data_length * 8 / base_spec.bits)

    # Adjust rows and columns
    cols = base_spec.size.cols
    rows = math.ceil(required_triangles / cols)

    # Adjust other parameters proportionally
    scale_factor = math.sqrt(rows / base_spec.size.rows)

    spec = Specification(
        bits=base_spec.bits,
        size=Size(rows=rows, cols=cols),
        white_frame_pad=Pad(
            *(p * scale_factor for p in astuple(base_spec.white_frame_pad))
        ),
        black_background_pad=Pad(
            *(p * scale_factor for p in astuple(base_spec.black_background_pad))
        ),
        white_strip_height=base_spec.white_strip_height * scale_factor,
        row_inset=base_spec.row_inset * scale_factor,
        triangle_dim=Dim(*(d * scale_factor for d in astuple(base_spec.triangle_dim))),
    )

    # Adjust dimensions to fit within max_width and max_height
    barcode_dimensions = barcode_dim(spec)
    width_scale = max_width / barcode_dimensions.width
    height_scale = max_height / barcode_dimensions.height
    final_scale = min(width_scale, height_scale)

    return Specification(
        bits=spec.bits,
        size=spec.size,
        white_frame_pad=Pad(*(p * final_scale for p in astuple(spec.white_frame_pad))),
        black_background_pad=Pad(
            *(p * final_scale for p in astuple(spec.black_background_pad))
        ),
        white_strip_height=spec.white_strip_height * final_scale,
        row_inset=spec.row_inset * final_scale,
        triangle_dim=Dim(*(d * final_scale for d in astuple(spec.triangle_dim))),
    )


def barcode(spec, width, height, data, error_correction_level):
    # Determine Reed-Solomon error correction symbols
    ecc_symbols = {
        "L": max(7, len(data) // 5),
        "M": max(10, len(data) // 4),
        "Q": max(13, len(data) // 3),
        "H": max(17, len(data) // 2),
    }[error_correction_level]

    # Apply Reed-Solomon encoding
    encoded_data = apply_reed_solomon(data, ecc_symbols)

    dwg = svgwrite.Drawing(size=(width, height))

    dim = barcode_dim(spec)
    outer_rect = Rect(Point(0, 0), dim)
    inner_rect = Rect(
        Point(spec.white_frame_pad.left, spec.white_frame_pad.top),
        Dim(
            dim.width - spec.white_frame_pad.left - spec.white_frame_pad.right,
            dim.height - spec.white_frame_pad.top - spec.white_frame_pad.bottom,
        ),
    )
    inner_padded_rect = Rect(
        Point(
            inner_rect.point.x + spec.black_background_pad.left,
            inner_rect.point.y + spec.black_background_pad.top,
        ),
        Dim(
            inner_rect.dim.width
            - spec.black_background_pad.left
            - spec.black_background_pad.right,
            inner_rect.dim.height
            - spec.black_background_pad.top
            - spec.black_background_pad.bottom,
        ),
    )

    draw_frame(dwg, outer_rect, inner_rect)

    row_spec = get_row_spec(spec)
    colored_data = colors_prefix(spec.bits) + data_to_colors(spec.bits, encoded_data)

    draw_triangles(dwg, spec, inner_padded_rect.point, colored_data)
    draw_strips(dwg, row_spec, inner_padded_rect.point, spec.size)

    return dwg.tostring()

def generate_hccb(data: Union[str, bytes], width, height, error_correction_level='M'):
    # Convert data to bytes if it's a string
    if isinstance(data, str):
        data = list(data.encode('utf-8'))
    elif isinstance(data, bytes):
        data = list(data)

    # Calculate dynamic specifications based on data length and target dimensions
    spec = calculate_dynamic_spec(len(data), width, height)

    # Generate the barcode
    svg_string = barcode(spec, width, height, data, error_correction_level)
    return svg_string


# Example usage
example_text = "The reader is so hard, I don't want to write it, is there any expert who can write the decoder?"  # Example text data
svg_string = generate_hccb(example_text, 500, 500, error_correction_level="Q")

# Save the SVG to a file
with open("hccb_barcode.svg", "w") as f:
    f.write(svg_string)
