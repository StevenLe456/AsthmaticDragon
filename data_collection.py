import datetime
import os
import time
from collections import deque

import cv2
import keyboard
import numpy as np
import pandas as pd
import torch

from neural_methods.model.BigSmall import BigSmall

N_SEG = 3              # frames per model window (BigSmall frame depth)
BIG_SIZE = 144         # Big branch input
SMALL_SIZE = 9         # Small branch input
TARGET_FPS = 25        # rate the model was trained at (BP4D+)
BUF_SECONDS = 12       # rolling PPG buffer length
MIN_SECONDS = 8        # wait this long before estimating HR
LOW_HZ, HIGH_HZ = 0.7, 3.0
DETECT_EVERY = 10      # run face detector every N processed frames
BOX_SCALE = 1.5        # enlarge detected box (toolbox uses a larger box)
INTEGRATE_OUTPUT = False  # True if your config's label type is a derivative
                          # (e.g. DiffNormalized). VERIFY against the config.
BIG_STANDARDIZE = False   # True if the loader standardizes Big frames. VERIFY

record = False


class FaceTracker:
    def __init__(self):
        path = os.path.join("cv_data", "haarcascade_frontalface_default.xml")
        self.det = cv2.CascadeClassifier(path)
        self.box = None  # (cx, cy, w, h) smoothed
        self.n = 0

    def update(self, frame):
        if self.box is None or self.n % DETECT_EVERY == 0:
            scale = 0.5  # detect on a half-size gray image for speed
            gray = cv2.cvtColor(cv2.resize(frame, None, fx=scale, fy=scale),
                                cv2.COLOR_BGR2GRAY)
            faces = self.det.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
            if len(faces):
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                x /= scale
                y /= scale
                w /= scale
                h /= scale
                new = np.array([x + w / 2, y + h / 2, w, h], dtype=np.float32)
                self.box = new if self.box is None else 0.7 * self.box + 0.3 * new
        self.n += 1
        return self.box

    def crop(self, frame):
        if self.box is None:
            return None
        cx, cy, w, h = self.box
        s = max(w, h) * BOX_SCALE
        x0, y0 = int(max(cx - s / 2, 0)), int(max(cy - s / 2, 0))
        x1 = int(min(cx + s / 2, frame.shape[1]))
        y1 = int(min(cy + s / 2, frame.shape[0]))
        if x1 - x0 < 20 or y1 - y0 < 20:
            return None
        return frame[y0:y1, x0:x1], (x0, y0, x1, y1)


def load_model(weights):
    model = BigSmall(n_segment=N_SEG)  # defaults match the multitask release
    state = torch.load(weights, map_location="cpu")
    state = {k.replace("module.", ""): v for k, v in state.items()}
    model.load_state_dict(state)
    return model.eval()


class WindowProcessor:
    """Collects frames, builds (big, small) inputs, and runs the model."""

    def __init__(self, model):
        self.model = model
        self.big = deque(maxlen=N_SEG + 1)
        self.small = deque(maxlen=N_SEG + 1)
        self.diff_std = None  # running std for diff normalization

    def push(self, crop_bgr):
        rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        big = cv2.resize(rgb, (BIG_SIZE, BIG_SIZE),
                         interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        small = cv2.resize(rgb, (SMALL_SIZE, SMALL_SIZE),
                           interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        self.big.append(big)
        self.small.append(small)
        if len(self.big) < N_SEG + 1:
            return None

        bigs = np.stack(list(self.big)[:N_SEG])
        sm = np.stack(self.small)
        diffs = (sm[1:] - sm[:-1]) / (sm[1:] + sm[:-1] + 1e-7)

        # The toolbox divides by the std over the whole video; use a running
        # estimate instead for streaming.
        cur = float(diffs.std()) + 1e-7
        self.diff_std = cur if self.diff_std is None else 0.99 * self.diff_std + 0.01 * cur
        diffs = diffs / self.diff_std

        if BIG_STANDARDIZE:
            bigs = (bigs - bigs.mean()) / (bigs.std() + 1e-7)

        big_t = torch.from_numpy(bigs.transpose(0, 3, 1, 2).copy())
        small_t = torch.from_numpy(diffs.transpose(0, 3, 1, 2).copy())

        with torch.no_grad():
            au, bvp, resp = self.model([big_t, small_t])  # (au, bvp, resp)
        out = au.detach().cpu().numpy().ravel(), bvp.detach().cpu().numpy().ravel(), resp.detach().cpu().numpy().ravel()

        # Keep the newest frame as the start of the next (non-overlapping) window
        last_big, last_small = self.big[-1], self.small[-1]
        self.big.clear(); self.small.clear()
        self.big.append(last_big); self.small.append(last_small)
        return out


# ----------------------------- signal processing ---------------------------
# def clean_signal(raw, fs):
#     sig = np.cumsum(raw) if INTEGRATE_OUTPUT else np.asarray(raw, dtype=np.float64)
#     sig = sig - np.mean(sig)
#     sos = butter(3, [LOW_HZ, HIGH_HZ], btype="bandpass", fs=fs, output="sos")
#     return sosfiltfilt(sos, sig)


def on_r(event):
    if event.name == 'r':
        global record
        record = not record
        print(record)


def main():
    breathing_pattern = input("What breathing pattern are you recording in this session? ")
    directory = os.path.join("data", breathing_pattern)
    if not os.path.exists(directory):
        os.makedirs(directory)

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    model = load_model("final_model_release/BP4D_BigSmall_Multitask_Fold1.pth")
    proc = WindowProcessor(model)
    tracker = FaceTracker()

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    last_taken = 0.0
    period = 1.0 / TARGET_FPS

    data = []

    print_once = True

    keyboard.on_press_key('r', on_r)

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        now = time.time()
        if record:
            if print_once:
                print("Recording")
                print_once = False
        else:
            if data:
                print("Stop recording")
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                df = pd.DataFrame(data)
                filename = f"{breathing_pattern}_{timestamp}.csv"
                pth = os.path.join(directory, filename)
                df.to_csv(pth)
                data = []
                print_once = True

        # Subsample to the model's training frame rate using wall-clock time
        if now - last_taken >= period:
            last_taken = now
            tracker.update(frame)
            res = tracker.crop(frame)
            if res is not None:
                print("Face detected")
                crop, (x0, y0, x1, y1) = res
                cv2.rectangle(frame, (x0, y0), (x1, y1), (255, 200, 0), 2)
                out = proc.push(crop)
                if out is not None and record:
                    au_val = np.argmax(out[0])
                    for i, j in zip(out[1], out[2]):
                        data.append({"au": au_val, "bvp": i, "resp": j})
            else:
                # Lost the face: reset so we don't stitch across a gap
                proc.big.clear(); proc.small.clear()
                print("Face not detected")

        if keyboard.is_pressed('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
