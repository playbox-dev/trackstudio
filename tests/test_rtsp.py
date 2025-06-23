import cv2


def test_rtsp():
    cap = cv2.VideoCapture("rtsp://localhost:8554/camera1", cv2.CAP_FFMPEG)
    for i in range(10):
        ret, frame = cap.read()
        cv2.imwrite(f"tests/frame_{i}.jpg", frame)
        if not ret:
            break
    cap.release()
