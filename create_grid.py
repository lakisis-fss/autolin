import cv2
import numpy as np
import os

def create_grid(image_path, output_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read {image_path}")
        return
        
    h, w = img.shape[:2]
    
    # Draw horizontal lines and numbers
    for y in range(0, h, 100):
        cv2.line(img, (0, y), (w, y), (128, 128, 128), 1)
        cv2.putText(img, str(y), (5, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
    # Draw vertical lines and numbers
    for x in range(0, w, 100):
        cv2.line(img, (x, 0), (x, h), (128, 128, 128), 1)
        cv2.putText(img, str(x), (x + 5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
    cv2.imwrite(output_path, img)
    print(f"Grid screenshot saved to {output_path}")

if __name__ == "__main__":
    create_grid('docs/03_test_capture.png', 'docs/05_screenshot_grid.png')
