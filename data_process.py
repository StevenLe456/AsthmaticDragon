import os
import pickle

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt

BVP_LOW = 0.7
BVP_HIGH = 3.0
RESP_LOW = 0.1
RESP_HIGH = 0.5
TARGET_FPS = 25

#----------------------------- signal processing ---------------------------
def clean_signal(raw, fs, low, high):
    sig = np.asarray(raw, dtype=np.float64)
    sig = sig - np.mean(sig)
    sos = butter(3, [low, high], btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, sig)

def main():
    train_x = []
    train_y = []
    test_x = []
    test_y = []

    normal = 0
    box = 0
    inhaler = 0

    for root, dirs, files in os.walk("data"):
        for f in files:
            path = os.path.join(root, f)
            df = pd.read_csv(path)
            bvp = df["bvp"].to_numpy()
            resp = df["resp"].to_numpy()
            bvp = clean_signal(bvp, TARGET_FPS, BVP_LOW, BVP_HIGH)
            resp = clean_signal(resp, TARGET_FPS, RESP_LOW, RESP_HIGH)
            i = np.stack([bvp, resp]).tolist()
            j = -1
            if "normal" in path:
                j = 0
                normal += 1
            elif "box" in path:
                j = 1
                box += 1
            elif "inhaler" in path:
                j = 2
                inhaler += 1
            else:
                print("Error...")
            if (j == 0 and normal <= 16) or (j == 1 and box <= 16) or (j == 2 and inhaler <= 16):
                train_x.append(i)
                train_y.append(j)
            elif (j == 0 and normal > 16) or (j == 1 and box > 16) or (j == 2 and inhaler > 16):
                test_x.append(i)
                test_y.append(j)
            else:
                print("Error...")

    data = {"train": [train_x, train_y], "test": [test_x, test_y]}

    with open("data/data.pickle", "wb") as p:
        pickle.dump(data, p)

if __name__ == "__main__":
    main()