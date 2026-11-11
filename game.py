import arcade
import os

WIDTH = 800
HEIGHT = 650
TITLE = "Asthmatic Dragon"
CHARA_SCALE = 0.6
CHARA_SPEED = 4
CHARA_BOUNDS = [-40, 740]
INHALER_SCALE = 0.25
FIRE_SCALE = 0.1
FIRE_SPEED = 6
FIRE_OFFSET = 54
BUNNY_SCALE = 0.5
BUNNY_OFFSET = 50
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
        self.scene.add_sprite_list("Bunny")

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

        # Initialize dust bunnies here
        for i in [0, 1, 3, 4, 6, 7]:
            bunners = Bunny(os.path.join("assets", "sprites", "sprite_5.png"), BUNNY_SCALE, "large")
            bunners.center_x = i * WIDTH / 8 + BUNNY_OFFSET
            bunners.center_y = HEIGHT - 60
            bunners.change_y = -0.5
            self.scene.add_sprite("Bunny", bunners)

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
        self.scene.update(delta_time, ["Fire", "Bunny"]) # type: ignore

        # Bullet collision and out-of-bounds logic
        for b in self.scene.get_sprite_list("Fire"): # type: ignore
            hit = arcade.check_for_collision_with_lists(
                b,
                [
                    self.scene["Bunny"] # type: ignore
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
                            b1.center_y = collision.center_y - 12
                            b1.change_y = -2
                            self.scene.add_sprite("Bunny", b1) # type: ignore
                            b2 = Bunny(os.path.join("assets", "sprites", "sprite_7.png"), SMALLEST_BUN_SCALE, "small")
                            b2.center_x = collision.center_x + 12
                            b2.center_y = collision.center_y + 12
                            b2.change_y = -2
                            self.scene.add_sprite("Bunny", b2) # type: ignore
                            b3 = Bunny(os.path.join("assets", "sprites", "sprite_7.png"), SMALLEST_BUN_SCALE, "small")
                            b3.center_x = collision.center_x + 12
                            b3.center_y = collision.center_y - 12
                            b3.change_y = -2
                            self.scene.add_sprite("Bunny", b3) # type: ignore
                            b4 = Bunny(os.path.join("assets", "sprites", "sprite_7.png"), SMALLEST_BUN_SCALE, "small")
                            b4.center_x = collision.center_x - 12
                            b4.center_y = collision.center_y + 12
                            b4.change_y = -2
                            self.scene.add_sprite("Bunny", b4) # type: ignore
                        else:
                            pass
                        collision.remove_from_sprite_lists()
            if b.bottom > HEIGHT:
                b.remove_from_sprite_lists()

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