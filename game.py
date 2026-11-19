import arcade
from collections import deque
import cv2
from neural_methods.model.BigSmall import BigSmall
import numpy as np
import os
import pandas as pd
import random
from scipy.signal import butter, sosfiltfilt
import time
import torch
from sktime.base import load
from sktime.classification.feature_based import TSFreshClassifier
from sktime.transformations.interpolate import TSInterpolator

DETECT_EVERY = 10
BOX_SCALE = 1.5
N_SEG = 3
BIG_SIZE = 144
SMALL_SIZE = 9
BIG_STANDARDIZE = False
TARGET_FPS = 25
BVP_LOW = 0.7
BVP_HIGH = 3.0
RESP_LOW = 0.1
RESP_HIGH = 0.5
WIDTH = 1000
HEIGHT = 650
TITLE = "Asthmatic Dragon"
CHARA_SCALE = 0.6
CHARA_SPEED = 6
CHARA_BOUNDS = [-40, WIDTH - 60]
INHALER_SCALE = 0.25
FIRE_SCALE = 0.1
FIRE_SPEED = 8
FIRE_OFFSET = 54
BUNNY_SCALE = 0.5
SMALLER_BUN_SCALE = 0.25
SMALLEST_BUN_SCALE = 0.12

def to_nested_dataframe(recordings, channel_names=None):
    """Convert arrays of shape (timepoints, channels) to an sktime panel."""
    if len(recordings) == 0:
        raise ValueError("At least one recording is required.")

    arrays = [np.asarray(recording, dtype=np.float64)
              for recording in recordings]

    if any(array.ndim != 2 for array in arrays):
        raise ValueError(
            "Each recording must have shape (n_timepoints, n_channels)."
        )

    n_channels = arrays[0].shape[1]
    if n_channels == 0:
        raise ValueError("Recordings must contain at least one channel.")

    for i, array in enumerate(arrays):
        if array.shape[1] != n_channels:
            raise ValueError(f"Recording {i} has a different channel count.")
        if array.shape[0] < 2:
            raise ValueError(
                f"Recording {i} needs at least two points for interpolation."
            )
        if not np.isfinite(array).all():
            raise ValueError(
                f"Recording {i} contains NaN or infinite values; "
                "handle these before using this template."
            )

    if channel_names is None:
        channel_names = [f"channel_{j}" for j in range(n_channels)]
    else:
        channel_names = list(channel_names)

    if len(channel_names) != n_channels:
        raise ValueError("channel_names must match the number of channels.")
    if len(set(channel_names)) != n_channels:
        raise ValueError("Channel names must be unique.")

    return pd.DataFrame({
        name: [pd.Series(array[:, j]) for array in arrays]
        for j, name in enumerate(channel_names)
    })

def capture(cap, record, data, scaler, fresh, last_taken, period, tracker, proc):
    ok, frame = cap.read()
    if not ok:
        return ""
    now = time.time()
    if record:
        # Subsample to the model's training frame rate using wall-clock time
        if now - last_taken >= period:
            last_taken = now
            tracker.update(frame)
            res = tracker.crop(frame)
            if res is not None:
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
                return "no-face"
    else:
        if data:
            df = pd.DataFrame(data)
            # Process data here
            bvp = df["bvp"].to_numpy()
            resp = df["resp"].to_numpy()
            bvp = clean_signal(bvp, TARGET_FPS, BVP_LOW, BVP_HIGH)
            resp = clean_signal(resp, TARGET_FPS, RESP_LOW, RESP_HIGH)
            x = np.stack([bvp, resp]).T.tolist()
            channels = ["bvp", "resp"]
            x = to_nested_dataframe([x], channels)
            x = scaler.fit_transform(x)
            pred = fresh.predict(x)
            classy = ""
            if pred == 0:
                classy = "box"
            elif pred == 1:
                classy = "inhaler"
            elif pred == 2:
                classy = "non-box (pause in breathing too short)"
            elif pred == 3:
                classy = "non-box (breathing in/out too short)"
            elif pred == 4:
                classy = "non-inhaler (forgot to exhale in the beginning)"
            elif pred == 5:
                classy = "non-inhaler (pause in breathing too short)"
            else:
                classy = "error"
            data = []
            return classy

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


def clean_signal(raw, fs, low, high):
    sig = np.asarray(raw, dtype=np.float64)
    sig = sig - np.mean(sig)
    sos = butter(3, [low, high], btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, sig)

class Dragon(arcade.Sprite):
    def __init__(self):
        super().__init__()
        self.scale = CHARA_SCALE
        self.textures = []
        self.textures.append(arcade.load_texture(os.path.join("assets", "sprites", "sprite_0.png")))
        self.textures.append(arcade.load_texture(os.path.join("assets", "sprites", "sprite_1.png")))
        self.texture = self.textures[0]
        self.fire_breathing = False

    def update_animation(self, delta_time):
        if self.fire_breathing:
            self.texture = self.textures[1]
        else:
            self.texture = self.textures[0]

class Bunny(arcade.Sprite):
    def __init__(self, texture, scale, sz):
        super().__init__()
        self.texture = arcade.load_texture(texture)
        self.scale = scale
        self.sz = sz

class Instructions(arcade.View):
    def __init__(self, cap, data, scaler, fresh1, fresh2, last_taken, period, tracker, proc):
        super().__init__()
        self.cap = cap
        self.data = data
        self.scaler = scaler
        self.inhaler = fresh1
        self.box = fresh2
        self.last_taken = last_taken
        self.period = period
        self.tracker = tracker
        self.proc = proc
        self.page = 0
        self.continue_text = "Press C to continue..."
        self.texts = [
            "You are a fire-breathing dragon on a mission to defeat the dust bunnies.\nYou do this by moving left with the A key or left arrow key,\nright with the D key or right arrow key,\nand the W key or up arrow key to spit out fire.",
            "The problem is that you have asthma.\nWhenever a dust dunny hits the ground, your asthma symptoms will flare up\nand it will be harder to breathe fire. You will lose the game when your symptoms become\ntoo severe and you can no longer breathe fire.",
            "Not to worry, there are inhalers you can equip by hitting with your fire\nto relieve your symptoms. There will be five inhalers overall in the game.",
            "When you equip the inhaler, you will be prompted to do the breathing exercise\ninvolved in correctly inhaling your medication. Press the R key to let the camera start\nrecording you breathing, and the R key again to stop.",
            "There will also be a power-up in the game that, when activated, will destroy all dust bunnies within its zone.\nWhen the power-up is fir with your fire, you will be prompted to complete a box breathing exercise.\nPress the R key to let the camera start recording you breathing, and the R key again to stop."
        ]
        self.current_text = arcade.Text(self.texts[self.page] + "\n\n" + self.continue_text, 10, HEIGHT - 50, multiline=True, width=WIDTH-50, font_size=24)

    def on_draw(self):
        self.window.clear()
        self.current_text.draw() # type: ignore

    def on_update(self, delta_time: float):
        if self.page == len(self.texts):
            toriel = InhalerTutorial(self.cap, self.data, self.scaler, self.inhaler, self.box, self.last_taken, self.period, self.tracker, self.proc)
            self.window.show_view(toriel)
        else:
            self.current_text.text = self.texts[self.page] + "\n\n" + self.continue_text

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK

    def on_key_release(self, symbol: int, modifiers: int):
        if symbol == arcade.key.C:
            self.page += 1

class InhalerTutorial(arcade.View):
    def __init__(self, cap, data, scaler, fresh1, fresh2, last_taken, period, tracker, proc):
        super().__init__()
        self.error = False
        self.cap = cap
        self.data = data
        self.scaler = scaler
        self.inhaler = fresh1
        self.box = fresh2
        self.last_taken = last_taken
        self.period = period
        self.tracker = tracker
        self.proc = proc
        self.record = False
        self.page = 0
        self.continue_text = "Press C to continue..."
        self.texts = [
            "Now, let's practice how to inhale your medication properly.",
            "To do this:\n1. Exhale completely.\n2. While breathing in, press down on your inhaler and breathe in fully.\n3. Hold in your breath for 10 seconds.\n4. Exhale slowly.",
            "Now, press the R key to record your breathing.\nPress the R key again to stop recording."
        ]
        self.current_text = arcade.Text(self.texts[self.page] + "\n\n" + self.continue_text, 10, HEIGHT - 50, multiline=True, width=WIDTH-50, font_size=24)
        self.classy = ""

    def on_draw(self):
            self.window.clear()
            self.current_text.draw() # type: ignore

    def on_update(self, delta_time: float):
        if self.error and self.page == len(self.texts) + 1:
            self.error = False
            self.page = 1
            self.data = []
        if self.page == len(self.texts) - 1:
            self.classy = capture(self.cap, self.record, self.data, self.scaler, self.inhaler, self.last_taken, self.period, self.tracker, self.proc)
            if not self.record and self.data:
                self.page += 1
        elif self.page == len(self.texts):
            if self.classy == "inhaler":
                self.current_text.text = "You successfully learned how to inhale your rescue medication!" + "\n\n" + self.continue_text
            else:
                self.error = True
                if self.classy == "non-inhaler (forgot to exhale in the beginning)":
                    self.current_text.text = "You forgot to exhale fully in the beginning." + "\n\n" + self.continue_text
                elif self.classy == "non-inhaler (pause in breathing too short)":
                    self.current_text.text = "You did not hold your breath long enough." + "\n\n" + self.continue_text
                else:
                    self.current_text.text = ""
        elif self.page == len(self.texts) + 1:
            next_toriel = BoxTutorial(self.cap, self.data, self.scaler, self.inhaler, self.box, self.last_taken, self.period, self.tracker, self.proc)
            self.window.show_view(next_toriel)
        else:
            self.current_text.text = self.texts[self.page] + "\n\n" + self.continue_text    
        if self.classy == "no-face":
            self.current_text.text = "Trying to detect face..."
        if self.page == len(self.texts) - 1:
            self.current_text.text = self.texts[self.page]

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
    
    def on_key_release(self, symbol: int, modifiers: int):
        if symbol == arcade.key.C:
            self.page += 1
        if symbol == arcade.key.R and self.page == len(self.texts) - 1:
            self.record = not self.record

class BoxTutorial(arcade.View):
    def __init__(self, cap, data, scaler, fresh1, fresh2, last_taken, period, tracker, proc):
        super().__init__()
        self.error = False
        self.cap = cap
        self.data = data
        self.scaler = scaler
        self.inhaler = fresh1
        self.box = fresh2
        self.last_taken = last_taken
        self.period = period
        self.tracker = tracker
        self.proc = proc
        self.record = False
        self.page = 0
        self.continue_text = "Press C to continue..."
        self.texts = [
            "Now, let's practice how to do box breathing.",
            "To do this:\n1. Inhale for 4 seconds.\n2. Hold your breath for 4 seconds.\n3. Exhale for 4 seconds.\n4. Hold your breath for 4 seconds.",
            "Now, press the R key to record your breathing.\nPress the R key again to stop recording."
        ]
        self.current_text = arcade.Text(self.texts[self.page] + "\n\n" + self.continue_text, 10, HEIGHT - 50, multiline=True, width=WIDTH-50, font_size=24)
        self.classy = ""

    def on_draw(self):
        self.window.clear()
        self.current_text.draw() # type: ignore
    
    def on_update(self, delta_time: float):
        if self.error and self.page == len(self.texts) + 1:
            self.error = False
            self.page = 1
            self.data = []
        if self.page == len(self.texts) - 1:
            self.classy = capture(self.cap, self.record, self.data, self.scaler, self.inhaler, self.last_taken, self.period, self.tracker, self.proc)
            if not self.record and self.data:
                self.page += 1
        elif self.page == len(self.texts):
            if self.classy == "box":
                self.current_text.text = "You successfully learned how to do box breathing!" + "\n\n" + self.continue_text
            else:
                self.error = True
                if self.classy == "non-box (pause in breathing too short)":
                    self.current_text.text = "You did not hold your breath long enough." + "\n\n" + self.continue_text
                elif self.classy == "non-box (breathing in/out too short)":
                    self.current_text.text = "You did not breathe in/out long enough." + "\n\n" + self.continue_text
                else:
                    self.current_text.text = ""
        elif self.page == len(self.texts) + 1:
            self.current_text.text = "You have completed the tutorials!\n\nPress C to continue to the game."
        elif self.page == len(self.texts) + 2:
            game = Game()
            self.window.show_view(game)
        else:
            self.current_text.text = self.texts[self.page] + "\n\n" + self.continue_text    
        if self.classy == "no-face":
            self.current_text.text = "Trying to detect face..."
        if self.page == len(self.texts) - 1:
            self.current_text.text = self.texts[self.page]

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
    
    def on_key_release(self, symbol: int, modifiers: int):
        if symbol == arcade.key.C:
            self.page += 1
        if symbol == arcade.key.R and self.page == len(self.texts) - 1:
            self.record = not self.record

class Game(arcade.View):
    def __init__(self):
        super().__init__()

        # Create scene and set to None
        self.scene = None

        # Sprite variables
        self.chara = None
        self.fire_sprite = None
        self.smiley_sprite = None
        self.big_bunny_sprite = None
        self.medium_bunny_sprite = None
        self.small_bunny_sprite = None

        # Physics engine
        self.physics_engine = None

        # Game states
        self.num_powerups = 0

        # Initialize scene and add sprite lists
        self.scene = arcade.Scene()
        self.scene.add_sprite_list("Player")
        self.scene.add_sprite_list("Inhalers")
        self.scene.add_sprite_list("Fire")
        self.scene.add_sprite_list("Bunny")
        self.scene.add_sprite_list("Smileys")

        # Initialize chara here
        self.chara = Dragon()
        self.chara.center_x = WIDTH / 2
        self.chara.center_y = HEIGHT / 9
        self.scene.add_sprite("Player", self.chara)

        # Initialize inhalers here
        for i in range(5):
            self.create_inhalers()

        # Initialize dust bunnies here
        for i in range(3):
            self.create_bunnies()

        # Initialize physics engine
        self.physics_engine = arcade.PhysicsEngineSimple(self.chara, self.scene.get_sprite_list("Inhalers"))

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK

    def create_inhalers(self):
        inhaler = arcade.Sprite(os.path.join("assets", "sprites", "sprite_3.png"), INHALER_SCALE)
        inhaler.center_x = random.uniform(25, WIDTH - 25)
        inhaler.center_y = random.uniform(200, HEIGHT - 50)
        self.scene.add_sprite("Inhalers", inhaler) # type: ignore
    
    def create_bunnies(self):
        bunners = Bunny(os.path.join("assets", "sprites", "sprite_5.png"), BUNNY_SCALE, "large")
        bunners.center_x = random.uniform(50, WIDTH - 50)
        bunners.center_y = HEIGHT - 60
        bunners.change_y = -0.5
        self.scene.add_sprite("Bunny", bunners) # type: ignore
    
    def on_draw(self):
        # Clear screen first
        self.clear()
        # Draw scene
        self.scene.draw() # type: ignore

    def on_update(self, delta_time: float):
        # Update player movement
        self.physics_engine.update() # type: ignore
        if self.chara.center_x < CHARA_BOUNDS[0]: # type: ignore
            self.chara.center_x = CHARA_BOUNDS[0] # type: ignore
        if self.chara.center_x > CHARA_BOUNDS[1]: # type: ignore
            self.chara.center_x = CHARA_BOUNDS[1] # type: ignore

        # Update player animation
        self.scene.update_animation(delta_time, ["Player"]) # type: ignore

        # Update bullet, enemies, and collectibles
        self.scene.update(delta_time, ["Fire", "Bunny"]) # type: ignore

        # Bullet collision and out-of-bounds logic
        for b in self.scene.get_sprite_list("Fire"): # type: ignore
            hit = arcade.check_for_collision_with_lists(
                b,
                [
                    self.scene["Bunny"], # type: ignore
                    self.scene["Smileys"] # type: ignore
                ]
            )
            if hit:
                b.remove_from_sprite_lists()
                for collision in hit:
                    if self.scene["Bunny"] in collision.sprite_lists: # type: ignore
                        if collision.sz == "large":
                            b1 = Bunny(os.path.join("assets", "sprites", "sprite_6.png"), SMALLER_BUN_SCALE, "medium")
                            b1.center_x = collision.center_x - 25
                            b1.center_y = collision.center_y
                            b1.change_y = -1
                            self.scene.add_sprite("Bunny", b1) # type: ignore
                            b2 = Bunny(os.path.join("assets", "sprites", "sprite_6.png"), SMALLER_BUN_SCALE, "medium")
                            b2.center_x = collision.center_x + 25
                            b2.center_y = collision.center_y
                            b2.change_y = -1
                            self.scene.add_sprite("Bunny", b2) # type: ignore
                        elif collision.sz == "medium":
                            b1 = Bunny(os.path.join("assets", "sprites", "sprite_7.png"), SMALLEST_BUN_SCALE, "small")
                            b1.center_x = collision.center_x - 12
                            b1.center_y = collision.center_y + 12
                            b1.change_y = -2
                            self.scene.add_sprite("Bunny", b1) # type: ignore
                            b2 = Bunny(os.path.join("assets", "sprites", "sprite_7.png"), SMALLEST_BUN_SCALE, "small")
                            b2.center_x = collision.center_x + 12
                            b2.center_y = collision.center_y + 12
                            b2.change_y = -2
                            self.scene.add_sprite("Bunny", b2) # type: ignore
                            b3 = Bunny(os.path.join("assets", "sprites", "sprite_7.png"), SMALLEST_BUN_SCALE, "small")
                            b3.center_x = collision.center_x
                            b3.center_y = collision.center_y - 12
                            b3.change_y = -2
                            self.scene.add_sprite("Bunny", b3) # type: ignore
                        else:
                            pass
                        collision.remove_from_sprite_lists()
                    elif self.scene["Smileys"] in collision.sprite_lists: # type: ignore
                        h = arcade.check_for_collision_with_lists(
                            collision,
                            [
                                self.scene["Bunny"] # type: ignore
                            ]
                        )
                        if h:
                            for c in h:
                                if self.scene["Bunny"] in c.sprite_lists: # type: ignore
                                    c.remove_from_sprite_lists()
                        collision.remove_from_sprite_lists()
                        self.num_powerups -= 1
                    else:
                        pass
            if b.bottom > HEIGHT:
                b.remove_from_sprite_lists()
            for b in self.scene.get_sprite_list("Bunny"): # type: ignore
                if b.top < 0:
                    b.remove_from_sprite_lists()

        # Randomly spawn powerups
        if random.random() < 0.007 and self.num_powerups < 2:
            x = random.uniform(100, 700)
            y = random.uniform(100, 400)
            smile = arcade.Sprite(os.path.join("assets", "sprites", "sprite_4.png"))
            smile.center_x = x
            smile.center_y = y
            smile.alpha = 100
            self.scene.add_sprite("Smileys", smile) # type: ignore
            self.num_powerups += 1

        if len(self.scene.get_sprite_list("Bunny")) == 0: # type: ignore
            for i in range(3):
                self.create_bunnies()

    def on_key_press(self, symbol, modifiers):
        if symbol == arcade.key.LEFT or symbol == arcade.key.A:
            self.chara.change_x -= CHARA_SPEED # type: ignore
        elif symbol == arcade.key.RIGHT or symbol == arcade.key.D:
            self.chara.change_x += CHARA_SPEED # type: ignore
        elif symbol == arcade.key.UP or symbol == arcade.key.W: # Shooting logic
            self.chara.fire_breathing = True # type: ignore
        else:
            pass

    def on_key_release(self, symbol, modifiers):
        if symbol == arcade.key.LEFT or symbol == arcade.key.A:
            self.chara.change_x = 0 # type: ignore
        elif symbol == arcade.key.RIGHT or symbol == arcade.key.D:
            self.chara.change_x = 0 # type: ignore
        elif symbol == arcade.key.UP or symbol == arcade.key.W: # Shooting logic
            self.chara.fire_breathing = False # type: ignore
            bullet = arcade.Sprite(os.path.join("assets", "sprites", "sprite_2.png"), FIRE_SCALE)
            bullet.change_y = FIRE_SPEED
            bullet.center_x = self.chara.center_x + FIRE_OFFSET # type: ignore
            bullet.bottom = self.chara.top # type: ignore
            self.scene.get_sprite_list("Fire").append(bullet) # type: ignore
        else:
            pass

class AsthmaticDragon:
    def __init__(self):
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        model = load_model("final_model_release/BP4D_BigSmall_Multitask_Fold1.pth")
        self.proc = WindowProcessor(model)
        self.tracker = FaceTracker()
        self.box = load("final_model_release/box")
        self.inhaler = load("final_model_release/inhaler")
        self.scaler = TSInterpolator(length=200)
    
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.last_taken = 0.0
        self.period = 1.0 / TARGET_FPS
    
        self.data = []

        self.window = arcade.Window(WIDTH, HEIGHT, TITLE)
        self.instruct = Instructions(self.cap, self.data, self.scaler, self.inhaler, self.box, self.last_taken, self.period, self.tracker, self.proc)
        self.window.show_view(self.instruct)

    def close(self):
        self.cap.release()
        cv2.destroyAllWindows()

def main():
    game = AsthmaticDragon()
    arcade.run()
    game.close()

if __name__ == "__main__":
    main()