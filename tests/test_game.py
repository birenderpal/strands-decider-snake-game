import pytest

from game import DIRECTIONS, HISTORY_LIMIT, Game


def test_eating_grows_and_places_food_off_the_snake():
    game = Game(6, [(2, 2), (1, 2), (0, 2)], (3, 2))
    game.advance("RIGHT")
    assert game.snake == [(3, 2), (2, 2), (1, 2), (0, 2)]
    assert game.score == 1
    assert game.moves == 1
    assert game.food not in game.snake


@pytest.mark.parametrize("direction", ["UP", "RIGHT", "DOWN", "LEFT"])
def test_normal_move_keeps_length(direction):
    game = Game(6, [(2, 2)], (5, 5))
    dx, dy = DIRECTIONS[direction]
    game.advance(direction)
    assert game.snake == [(2 + dx, 2 + dy)]
    assert game.score == 0


def test_tail_square_is_available_when_it_moves_away():
    game = Game(6, [(1, 1), (2, 1), (2, 2), (1, 2)], (5, 5))
    assert game.obstacle((1, 2)) is None
    game.advance("DOWN")
    assert game.status == "active"
    assert game.snake == [(1, 2), (1, 1), (2, 1), (2, 2)]


@pytest.mark.parametrize(
    ("snake", "direction", "reason"),
    [
        ([(0, 2)], "LEFT", "wall"),
        ([(2, 2), (1, 2), (0, 2)], "LEFT", "body"),
    ],
)
def test_collisions_end_game_without_inventing_a_move(snake, direction, reason):
    game = Game(6, snake.copy(), (5, 5))
    game.advance(direction)
    assert game.status == "lost"
    assert reason in game.message
    assert game.snake == snake
    assert game.moves == 1
    before = game.snapshot()
    with pytest.raises(ValueError):
        game.advance("UP")
    assert game.snapshot() == before


def test_filling_the_board_wins():
    game = Game(2, [(0, 0), (0, 1), (1, 1)], (1, 0))
    game.advance("RIGHT")
    assert game.status == "won"
    assert game.food is None
    assert len(game.snake) == 4


def test_invalid_move_cannot_change_the_board():
    game = Game.new()
    before = game.snapshot()
    with pytest.raises(ValueError):
        game.advance("DIAGONAL")
    assert game.snapshot() == before


def test_observation_exposes_obstacles_without_selecting_a_direction():
    game = Game.new()
    observation = game.observation()
    assert "Food is 4 squares RIGHT and same row" in observation
    assert "LEFT: crashes into the body; game over." in observation
    assert "RIGHT: no collision. Distance to food after moving: 3 squares." in observation
    assert all(direction in observation for direction in DIRECTIONS)


def test_observation_uses_tail_vacancy_and_preserves_fatal_choices():
    game = Game(6, [(0, 0), (1, 0), (1, 1), (0, 1)], (0, 4))
    observation = game.observation()
    assert "Food is same column and 4 squares DOWN" in observation
    assert "DOWN: no collision. Distance to food after moving: 3 squares." in observation
    assert "RIGHT: crashes into the body; game over." in observation
    assert "UP: crashes into the wall; game over." in observation
    assert "LEFT: crashes into the wall; game over." in observation


def test_full_board_and_tail_order_are_available_to_the_model():
    game = Game(6, [(2, 2), (2, 3), (1, 3)], (5, 5))
    observation = game.observation()
    assert "Board: 6 by 6" in observation
    assert "Snake from head to tail: [(2, 2), (2, 3), (1, 3)]. Food: (5, 5)" in observation
    assert "RIGHT increases x; DOWN increases y" in observation


def test_history_exposes_circling_without_banning_revisited_moves():
    game = Game(6, [(2, 2)], (5, 5))
    for direction in ["RIGHT", "DOWN", "LEFT", "UP"]:
        game.advance(direction)
    assert game.moves_since_food == 4
    assert game.head_revisits == 1
    observation = game.observation()
    assert "Recent moves, oldest first: RIGHT, DOWN, LEFT, UP." in observation
    assert "RIGHT: no collision." in observation
    assert "Recent visits to this destination: 1." in observation
    assert game.snapshot()["head_revisits"] == 1
    assert game.snapshot()["moves_since_food"] == 4


def test_eating_resets_target_specific_visits_but_preserves_recent_moves():
    game = Game(6, [(2, 2)], (2, 1))
    for direction in ["RIGHT", "DOWN", "LEFT", "UP", "UP"]:
        game.advance(direction)
    assert game.score == 1
    assert game.moves_since_food == 0
    assert game.head_revisits == 0
    assert "Recent moves, oldest first: RIGHT, DOWN, LEFT, UP, UP." in game.observation()
    assert "Recent visits to this destination: 1." not in game.observation()


def test_history_stays_bounded_during_a_long_loop():
    game = Game(6, [(2, 2)], (5, 5))
    for direction in ["RIGHT", "DOWN", "LEFT", "UP"] * 100:
        game.advance(direction)
    assert game.moves_since_food == 400
    assert game.head_revisits == HISTORY_LIMIT // 4 - 1
    assert "Recent moves, oldest first: RIGHT, DOWN, LEFT, UP, RIGHT, DOWN, LEFT, UP." in (
        game.observation()
    )
    assert len(game.observation()) < 1400


def test_reset_starts_with_no_previous_history():
    game = Game.new()
    game.advance("UP")
    reset = Game.new()
    assert reset.moves_since_food == 0
    assert reset.head_revisits == 0
    assert "Recent moves, oldest first: none." in reset.observation()
