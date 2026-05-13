import cv2
import numpy as np
import os

def find_potential_bars(image_path, output_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read {image_path}")
        return
        
    debug_img = img.copy()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    
    # Define color ranges
    colors = {
        'Red': ([0, 100, 100], [10, 255, 255]),
        'Red2': ([160, 100, 100], [180, 255, 255]),
        'Green': ([40, 100, 100], [80, 255, 255]),
        'Blue': ([100, 100, 100], [140, 255, 255]),
        'Yellow': ([20, 100, 100], [40, 255, 255]),
        'White/Gray': ([0, 0, 150], [180, 50, 255])
    }
    
    count = 0
    for name, (lower, upper) in colors.items():
        mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            # Filter for bar-like shapes
            if 50 < w < 800 and 5 < h < 60:
                count += 1
                color = (0, 255, 0) if "Green" in name else (0, 0, 255) if "Red" in name else (255, 255, 0)
                cv2.rectangle(debug_img, (x, y), (x + w, y + h), color, 2)
                cv2.putText(debug_img, f"#{count} {name}", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                print(f"Candidate #{count}: {name} at x={x}, y={y}, w={w}, h={h}")

    cv2.imwrite(output_path, debug_img)
    print(f"Debug image saved to {output_path}")

if __name__ == "__main__":
    find_potential_bars('docs/03_test_capture.png', 'docs/04_all_potential_bars.png')
