import arcade
import os

WIDTH = 800
HEIGHT = 600
TITLE = "Asthmatic Dragon"
CHARA_SCALE = 0.6
CHARA_SPEED = 4
CHARA_BOUNDS = [-40, 740]
INHALER_SCALE = 0.25
FIRE_SCALE = 0.1
FIRE_SPEED = 6
FIRE_OFFSET = 54

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

class Game(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        arcade.set_background_color(arcade.color.BLACK)
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

    def setup(self):
        # Initialize scene and add sprite lists
        self.scene = arcade.Scene()
        self.scene.add_sprite_list("Player")
        self.scene.add_sprite_list("Inhalers")
        self.scene.add_sprite_list("Fire")

        # Initialize chara here
        self.chara = Dragon()
        self.chara.center_x = WIDTH / 2
        self.chara.center_y = HEIGHT / 9
        self.scene.add_sprite("Player", self.chara)

        # Initialize inhalers here
        inhaler_offset_x = 60
        inhaler_offset_y = 50
        for i in [1, 3]:
            for j in range(3):
                inhaler = arcade.Sprite(os.path.join("assets", "sprites", "sprite_3.png"), INHALER_SCALE)
                inhaler.center_x = i * WIDTH / 5 + inhaler_offset_x
                inhaler.center_y = (8 - j) * HEIGHT / 8 - inhaler_offset_y
                self.scene.add_sprite("Inhalers", inhaler)

        # Initialize physics engine
        self.physics_engine = arcade.PhysicsEngineSimple(self.chara, self.scene.get_sprite_list("Inhalers"))

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
        self.scene.update(delta_time, ["Fire"]) # type: ignore

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
    game = Game(WIDTH, HEIGHT, TITLE)
    game.setup()
    arcade.run()


if __name__ == "__main__":
    main()