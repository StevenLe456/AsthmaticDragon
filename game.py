import arcade
import os
import random

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
    def __init__(self):
        super().__init__()
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
            toriel = Tutorial()
            self.window.show_view(toriel)
        else:
            self.current_text.text = self.texts[self.page] + "\n\n" + self.continue_text

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK

    def on_key_release(self, symbol: int, modifiers: int):
        if symbol == arcade.key.C:
            self.page += 1

class Tutorial(arcade.View):
    pass

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

def main():
    window = arcade.Window(WIDTH, HEIGHT, TITLE)
    instruct = Instructions()
    window.show_view(instruct)
    arcade.run()

if __name__ == "__main__":
    main()