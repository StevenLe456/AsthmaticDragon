import arcade

WIDTH = 800
HEIGHT = 600
TITLE = "Asthmatic Dragon"

class Game(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        arcade.set_background_color(arcade.color.BLACK)
        # Create sprite list variable here and set to None

    def setup(self):
        # Initialize sprite and sprite list here
        pass

    def on_draw(self):
        # Clear screen first
        self.clear()
        # Draw all sprites and sprite list here

    def on_update(self, delta_time: float):
        # All game logic goes here
        pass

    def on_key_press(self, symbol, modifiers):
        """
        Called whenever a key on the keyboard is pressed.

        For a full list of keys, see:
        https://api.arcade.academy/en/latest/arcade.key.html
        """
        pass

def main():
    game = Game(WIDTH, HEIGHT, TITLE)
    game.setup()
    arcade.run()


if __name__ == "__main__":
    main()