import cv2
import numpy as np
from reedsolo import RSCodec, ReedSolomonError

# Define the colors used in the HCCB code
FOUR_COLOR_MAP = [
    (0, 0, 0),  # black
    (255, 255, 69),  # yellow
    (18, 255, 14),  # green
    (255, 20, 0),  # red
]

EIGHT_COLOR_MAP = [
    (0, 0, 0),  # black
    (250, 253, 40),  # yellow
    (28, 236, 18),  # green
    (223, 2, 3),  # red
    (250, 250, 250),  # white
    (30, 246, 238),  # cyan
    (243, 139, 237),  # pink
    (24, 51, 222),  # blue
]


def find_hccb_code(image):
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Use edge detection to find potential HCCB codes
    edges = cv2.Canny(gray, 50, 150)

    # Find contours in the edged image
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    hccb_contour = None
    for contour in contours:
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) == 4:  # Looking for quadrilateral shapes
            hccb_contour = approx
            break

    if hccb_contour is None:
        raise ValueError("HCCB code not found in the image")

    # Get the bounding box of the contour
    x, y, w, h = cv2.boundingRect(hccb_contour)
    hccb_code = image[y : y + h, x : x + w]

    return hccb_code


def recognize_hccb(hccb_code, bits=3):
    # Convert the image to the correct color map
    color_map = EIGHT_COLOR_MAP if bits == 3 else FOUR_COLOR_MAP

    h, w, _ = hccb_code.shape
    rows, cols = h // 25, w // 25  # Assuming each triangle has a height of 25 pixels

    data = []
    for i in range(rows):
        for j in range(cols):
            x = j * 25
            y = i * 25
            color = hccb_code[y : y + 25, x : x + 25].mean(axis=(0, 1))  # Average color

            # Find the closest color in the color map
            closest_color = min(
                color_map, key=lambda c: np.linalg.norm(np.array(c) - color)
            )
            data.append(color_map.index(closest_color))

    return data


def restore_data(data, bits=3, ecc_symbols=68):
    rs = RSCodec(ecc_symbols)
    encoded_data = bytearray()

    mask = 3 if bits == 2 else 7
    shift = 2 if bits == 2 else 3

    for value in data:
        encoded_data.append((value & mask) << shift)

    try:
        restored_data = rs.decode(encoded_data)
        return list(restored_data)
    except ReedSolomonError:
        raise ValueError("Error in Reed-Solomon decoding")


def main():
    # Read the image
    image = cv2.imread("20240705134028.png")  # Replace with your image file path

    # Find and crop the HCCB code in the image
    hccb_code = find_hccb_code(image)

    cv2.imshow("HCCB Code", hccb_code)
    cv2.waitKey(0)

    # Recognize the HCCB code
    recognized_data = recognize_hccb(hccb_code)

    # Restore the original data
    restored_data = restore_data(recognized_data)

    print("Restored Data:", restored_data)


if __name__ == "__main__":
    main()
