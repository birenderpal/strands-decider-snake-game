"""Snake rules. This module describes the board; it never chooses a move."""

from collections import deque
from dataclasses import dataclass, field
from random import Random
from uuid import uuid4

DIRECTIONS = {"UP": (0, -1), "RIGHT": (1, 0), "DOWN": (0, 1), "LEFT": (-1, 0)}
Cell = tuple[int, int]
HISTORY_LIMIT = 64


@dataclass
class Game:
    size: int
    snake: list[Cell]
    food: Cell | None
    direction: str = "RIGHT"
    score: int = 0
    moves: int = 0
    status: str = "active"
    message: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    random: Random = field(default_factory=Random, repr=False)
    moves_since_food: int = 0
    _head_history: deque[Cell] = field(
        default_factory=lambda: deque(maxlen=HISTORY_LIMIT), init=False, repr=False
    )
    _move_history: deque[str] = field(
        default_factory=lambda: deque(maxlen=8), init=False, repr=False
    )

    def __post_init__(self):
        self._head_history.append(self.snake[0])

    @property
    def head_revisits(self) -> int:
        # Exclude the current occurrence. A revisit is evidence, not a forbidden move:
        # following the tail or taking a detour sometimes requires revisiting a cell.
        return self._head_history.count(self.snake[0]) - 1

    @classmethod
    def new(cls, seed: int | None = None) -> "Game":
        # A clear opening makes the first decision easy to follow on screen.
        return cls(12, [(5, 6), (4, 6), (3, 6)], (9, 6), random=Random(seed))

    def destination(self, direction: str) -> Cell:
        dx, dy = DIRECTIONS[direction]
        x, y = self.snake[0]
        return x + dx, y + dy

    def obstacle(self, cell: Cell) -> str | None:
        x, y = cell
        if not (0 <= x < self.size and 0 <= y < self.size):
            return "wall"
        # The tail vacates its square on a normal move, but stays when eating.
        occupied = self.snake if cell == self.food else self.snake[:-1]
        return "body" if cell in occupied else None

    def advance(self, direction: str) -> None:
        if self.status != "active":
            raise ValueError("This game has ended. Reset to play again.")
        if direction not in DIRECTIONS:
            raise ValueError("The model must choose UP, RIGHT, DOWN, or LEFT.")
        cell = self.destination(direction)
        obstacle = self.obstacle(cell)
        self.direction = direction
        self.moves += 1
        self.moves_since_food += 1
        self._move_history.append(direction)
        if obstacle:
            self.status = "lost"
            self.message = f"The snake hit a {obstacle}."
            return

        self.snake.insert(0, cell)
        if cell == self.food:
            self.score += 1
            self.moves_since_food = 0
            # Visits toward the old target must not discourage reaching a new food.
            self._head_history.clear()
            empty = [
                (x, y)
                for y in range(self.size)
                for x in range(self.size)
                if (x, y) not in self.snake
            ]
            self.food = self.random.choice(empty) if empty else None
            if not empty:
                self.status = "won"
                self.message = "The snake filled the board!"
        else:
            self.snake.pop()
        self._head_history.append(cell)

    def observation(self) -> str:
        """Expose board and bounded history without choosing or filtering moves."""
        if self.food is None:
            raise ValueError("There is no next move after the board is filled.")
        x, y = self.snake[0]
        food_x, food_y = self.food
        horizontal = (
            "same column"
            if food_x == x
            else f"{abs(food_x - x)} squares {'RIGHT' if food_x > x else 'LEFT'}"
        )
        vertical = (
            "same row"
            if food_y == y
            else f"{abs(food_y - y)} squares {'DOWN' if food_y > y else 'UP'}"
        )
        neighbors = []
        for direction in DIRECTIONS:
            cell = self.destination(direction)
            obstacle = self.obstacle(cell)
            content = f"crashes into the {obstacle}; game over." if obstacle else "no collision."
            # Manhattan distance is a sensor fact, not a searched path or move
            # recommendation. Include it for EVERY option, including fatal ones.
            distance = abs(cell[0] - food_x) + abs(cell[1] - food_y)
            neighbors.append(
                f"{direction}: {content} Distance to food after moving: {distance} squares. "
                f"Recent visits to this destination: {self._head_history.count(cell)}."
            )
        return (
            f"Snake game. Food is {horizontal} and {vertical} of the head.\n"
            + "\n".join(neighbors)
            + f"\nProgress: {self.moves_since_food} moves without eating. "
            f"The head has revisited its current square {self.head_revisits} times.\n"
            f"Visit counts cover the last {HISTORY_LIMIT} head positions since food changed.\n"
            f"Recent moves, oldest first: {', '.join(self._move_history) or 'none'}.\n"
            f"Board: {self.size} by {self.size}. Coordinates are (x, y), "
            f"0 to {self.size - 1}. RIGHT increases x; DOWN increases y.\n"
            f"Snake from head to tail: {self.snake}. Food: {self.food}.\n"
            "Unlisted squares are empty. The tail vacates its cell unless food is eaten.\n"
        )

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "size": self.size,
            "snake": [list(cell) for cell in self.snake],
            "food": list(self.food) if self.food else None,
            "direction": self.direction,
            "score": self.score,
            "moves": self.moves,
            "status": self.status,
            "message": self.message,
            "moves_since_food": self.moves_since_food,
            "head_revisits": self.head_revisits,
        }
