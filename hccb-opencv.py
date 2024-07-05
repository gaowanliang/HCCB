import cv2
import numpy as np
from scipy.spatial import distance
from reedsolo import RSCodec, ReedSolomonError

# Color constants (BGR format for OpenCV)
COLOR_MAP = {
    "BLACK": (0, 0, 0),
    "YELLOW": (0, 255, 255),
    "GREEN": (0, 255, 0),
    "RED": (0, 0, 255),
    "WHITE": (255, 255, 255),
    "CYAN": (255, 255, 0),
    "PINK": (203, 192, 255),
    "BLUE": (255, 0, 0),
}

COLOR_LIST = list(COLOR_MAP.keys())


def find_hccb(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter contours by area and shape
    possible_hccbs = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 1000:  # Adjust this threshold as needed
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            if len(approx) == 4:  # Assuming HCCB is roughly rectangular
                possible_hccbs.append(contour)

    if not possible_hccbs:
        return None

    # Choose the largest contour as the HCCB
    hccb_contour = max(possible_hccbs, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(hccb_contour)

    # Add a small margin
    margin = 10
    x, y = max(0, x - margin), max(0, y - margin)
    w, h = min(image.shape[1] - x, w + 2 * margin), min(
        image.shape[0] - y, h + 2 * margin
    )

    return image[y : y + h, x : x + w]


def determine_grid_size(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Detect lines
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10
    )

    cv2.imshow("Edges", edges)
    cv2.waitKey(0)

    # draw lines
    if lines is not None:
        temp = image.copy()
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(temp, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.imshow("Lines", temp)
        cv2.waitKey(0)

    if lines is None:
        return None, None

    # Separate horizontal and vertical lines
    horizontal_lines = []
    vertical_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(x2 - x1) > abs(y2 - y1):
            horizontal_lines.append(line)
        else:
            vertical_lines.append(line)

    # Count unique y-coordinates for horizontal lines and x-coordinates for vertical lines
    unique_y = set()
    unique_x = set()
    for line in horizontal_lines:
        unique_y.add(line[0][1])
    for line in vertical_lines:
        unique_x.add(line[0][0])

    rows = len(unique_y) - 1  # Subtract 1 because we count spaces between lines
    cols = len(unique_x) - 1

    return rows, cols


def classify_color(image, x, y):
    color = image[y, x]
    distances = {
        name: distance.euclidean(color, rgb) for name, rgb in COLOR_MAP.items()
    }
    return min(distances, key=distances.get)


def decode_colors(color_grid):
    bits = []
    for row in color_grid:
        for color in row:
            if color in ["BLACK", "YELLOW", "GREEN", "RED"]:
                bits.extend([int(x) for x in f"{COLOR_LIST.index(color):02b}"])
            else:
                bits.extend([int(x) for x in f"{COLOR_LIST.index(color):03b}"])
    return bytes(
        [int("".join(map(str, bits[i : i + 8])), 2) for i in range(0, len(bits), 8)]
    )


def read_hccb(image_path):
    # Load image
    image = cv2.imread(image_path)

    # Find and crop HCCB
    hccb_image = find_hccb(image)

    if hccb_image is None:
        print("No HCCB found in the image.")
        return None

    cv2.imshow("HCCB", hccb_image)
    cv2.waitKey(0)

    # Determine grid size
    rows, cols = determine_grid_size(hccb_image)
    if rows is None or cols is None:
        print("Failed to determine HCCB grid size.")
        return None

    print(f"Detected HCCB grid size: {rows} rows, {cols} columns")

    # Create a grid of sampling points
    height, width = hccb_image.shape[:2]
    x_step, y_step = width // (cols + 1), height // (rows + 1)

    # Read colors
    color_grid = []
    for i in range(1, rows + 1):
        row = []
        for j in range(1, cols + 1):
            x, y = j * x_step, i * y_step
            color = classify_color(hccb_image, x, y)
            row.append(color)
        color_grid.append(row)

    # Decode colors to data
    encoded_data = decode_colors(color_grid)

    # Apply Reed-Solomon decoding
    rsc = RSCodec(68)  # Adjust the number of error correction symbols as needed
    try:
        decoded_data = rsc.decode(encoded_data)
        return decoded_data[0]  # Return only the decoded message, not the RS encoding
    except ReedSolomonError:
        print("Too many errors to correct.")
        return None


# Usage
image_path = "20240705161648.png"
decoded_data = read_hccb(image_path)
if decoded_data:
    print("Decoded data:", decoded_data)
else:
    print("Failed to decode the barcode.")
