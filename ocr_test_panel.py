import cv2
import numpy as np
import mss
import re
from cv_state_reader import CVStateReader

def test_panel_ocr():
    # OCR 필터링을 완화한 테스트용 클래스
    class TestReader(CVStateReader):
        def extract_text_raw(self, img, roi_name):
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                
                resized = cv2.resize(img, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
                gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
                # 가우시안 블러로 노이즈 제거
                blurred = cv2.GaussianBlur(gray, (3, 3), 0)
                # Otsu 이진화로 자동 임계값 설정
                _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                # 흰 배경에 검은 글씨로 반전
                ocr_img = cv2.bitwise_not(thresh)
                
                # 디버그용 전처리 이미지 저장
                cv2.imwrite(f"docs/cv_debug/panel_thresh_{roi_name.lower()}.png", ocr_img)
                
                # OCR 설정: PSM 7 (한 줄 텍스트), 화이트리스트 적용
                custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789%.-'
                text = pytesseract.image_to_string(ocr_img, config=custom_config).strip()
                return text
            except Exception as e:
                return f"Error: {e}"

    reader = TestReader(debug=False)
    info = reader.get_lineage_rect()
    
    if not info:
        print("리니지 창을 찾을 수 없습니다. 게임을 실행 중인지 확인해 주세요.")
        return

    # 패널의 각 항목별 정밀 ROI 정의 (panel_full_search.png 분석 결과 기반)
    panel_rois = {
        "LEVEL":  {"x": 40,  "y": 770, "w": 40, "h": 25},
        "EXP":    {"x": 125, "y": 770, "w": 100, "h": 25},
        "AC":     {"x": 65,  "y": 815, "w": 45, "h": 25},
        "MR":     {"x": 160, "y": 815, "w": 45, "h": 25},
        "WEIGHT": {"x": 65,  "y": 855, "w": 45, "h": 25},
        "SP":     {"x": 160, "y": 855, "w": 45, "h": 25},
        "LAWFUL": {"x": 130, "y": 895, "w": 70, "h": 25}
    }

    print("="*50)
    print(f"{'항목':<15} | {'OCR 결과':<20}")
    print("-"*50)

    results = {}
    with mss.mss() as sct:
        for name, roi in panel_rois.items():
            # ROI 캡처를 위해 임시 등록
            reader.base_rois[name] = roi
            img = reader.capture_roi(info, name, sct)
            
            # OCR 수행
            text = reader.extract_text_raw(img, name)
            results[name] = text
            print(f"{name:<15} | {text}")
            
            # 디버그용 이미지 저장
            import os
            if not os.path.exists("docs/cv_debug"):
                os.makedirs("docs/cv_debug")
            cv2.imwrite(f"docs/cv_debug/panel_test_{name.lower()}.png", img)

    print("="*50)
    print("분석 완료. 결과는 docs/cv_debug/ocr_results.txt 에 저장되었습니다.")
    
    with open("docs/cv_debug/ocr_results.txt", "w", encoding="utf-8") as f:
        f.write("="*50 + "\n")
        f.write(f"{'ITEM':<15} | {'OCR RESULT':<20}\n")
        f.write("-"*50 + "\n")
        for name, text in results.items():
            f.write(f"{name:<15} | {text}\n")
        f.write("="*50 + "\n")

if __name__ == "__main__":
    test_panel_ocr()
