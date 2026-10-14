const $ = (id) => document.getElementById(id);
const arrows = { UP: "↑", RIGHT: "→", DOWN: "↓", LEFT: "←" };
const names = { UP: "Up", RIGHT: "Right", DOWN: "Down", LEFT: "Left" };
const canvas = $("board");
const ctx = canvas.getContext("2d");
let game = null;
let decision = null;
let model = { status: "loading", busy: false };
let running = false;
let pending = false;
let resetting = false;
let changingModel = false;
let generation = 0;
let timer = null;
let history = [];

async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(65000),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "The request failed.");
  return data;
}

function showError(message = "") {
  $("error").textContent = message;
  $("error").hidden = !message;
}

function acceptSnapshot(snapshot) {
  if (game && game.id !== snapshot.game.id) history = [];
  game = snapshot.game;
  decision = snapshot.decision;
  if (decision && history.at(-1)?.move !== decision.move) {
    history.push({ move: decision.move, choice: decision.choice });
    history = history.slice(-8);
  }
  render();
}

function drawBoard() {
  if (!game) return;
  const cell = canvas.width / game.size;
  ctx.fillStyle = "#23372d";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.lineWidth = 1;
  ctx.strokeStyle = "#33483a";
  ctx.beginPath();
  for (let i = 1; i < game.size; i++) {
    ctx.moveTo(i * cell, 0);
    ctx.lineTo(i * cell, canvas.height);
    ctx.moveTo(0, i * cell);
    ctx.lineTo(canvas.width, i * cell);
  }
  ctx.stroke();

  if (game.food) {
    const [x, y] = game.food.map((value) => (value + 0.5) * cell);
    ctx.shadowColor = "#f6a67b55";
    ctx.shadowBlur = 18;
    ctx.fillStyle = "#eea277";
    ctx.beginPath();
    ctx.arc(x, y + 1, cell * 0.21, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.strokeStyle = "#c8cf91";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(x, y - cell * 0.15);
    ctx.quadraticCurveTo(x, y - cell * 0.3, x + cell * 0.12, y - cell * 0.29);
    ctx.stroke();
  }

  const centers = game.snake.map(([x, y]) => [(x + 0.5) * cell, (y + 0.5) * cell]);
  const gradient = ctx.createLinearGradient(...centers.at(-1), ...centers[0]);
  gradient.addColorStop(0, "#8aa957");
  gradient.addColorStop(1, "#c9f18a");
  ctx.strokeStyle = gradient;
  ctx.lineWidth = cell * 0.67;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  centers.forEach(([x, y], index) => index ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.stroke();

  const [headX, headY] = centers[0];
  const side = cell * 0.73;
  ctx.fillStyle = game.status === "lost" ? "#d8b07e" : "#cff293";
  ctx.beginPath();
  ctx.roundRect(headX - side / 2, headY - side / 2, side, side, cell * 0.2);
  ctx.fill();
  const vectors = { UP: [0, -1], RIGHT: [1, 0], DOWN: [0, 1], LEFT: [-1, 0] };
  const [dx, dy] = vectors[game.direction];
  ctx.fillStyle = "#294030";
  for (const sign of [-1, 1]) {
    ctx.beginPath();
    ctx.arc(
      headX + dx * cell * 0.16 - dy * sign * cell * 0.16,
      headY + dy * cell * 0.16 + dx * sign * cell * 0.16,
      cell * 0.045, 0, Math.PI * 2,
    );
    ctx.fill();
  }
  canvas.setAttribute("aria-label",
    `Snake board. Score ${game.score}, ${game.moves} ${game.moves === 1 ? "move" : "moves"}. Head at ${game.snake[0]}. ` +
    `Food at ${game.food || "none"}. Game status: ${game.status}.`);
}

function setMessage(kicker, title, copy, centered = false) {
  $("board-message").hidden = !title;
  $("board-message").classList.toggle("centered", centered);
  $("message-kicker").textContent = kicker;
  $("message-title").textContent = title;
  $("message-copy").textContent = copy;
}

function setModel(nextModel) {
  const select = $("model-select");
  const changed = nextModel.model !== model.model;
  const options = nextModel.models || [];
  const ids = options.map((option) => option.id).join("\n");
  if (select.dataset.models !== ids) {
    select.replaceChildren(...options.map((item) => new Option(item.label, item.id)));
    select.dataset.models = ids;
    select.value = nextModel.model;
  } else if (changed) {
    select.value = nextModel.model;
  }
  model = nextModel;
}

function render() {
  const ready = model.status === "ready";
  const active = game?.status === "active";
  const occupied = pending || model.busy || changingModel;
  $("play").disabled = !game || !ready || !active || resetting || (!running && occupied);
  $("step").disabled = !game || !ready || !active || running || occupied || resetting;
  $("reset").disabled = !game || resetting || changingModel;
  const selected = model.models?.find((item) => item.id === $("model-select").value);
  const loading = model.status === "loading" || changingModel;
  $("model-select").disabled = loading || !model.models?.length;
  $("load-model").disabled = loading || occupied || running || resetting || !selected
    || (selected.id === model.model && ready);
  $("load-model").textContent = loading ? "Loading…" : model.status === "error" && selected?.id === model.model
    ? "Retry load" : "Load model";
  $("model-note").textContent = selected?.note || "Checking available models.";
  $("model-switch-note").textContent = loading
    ? "Loading model files. Downloads may take several minutes; progress appears in the server terminal."
    : running || pending || model.busy ? "Pause and wait for the current decision before changing models."
    : "Loading a different model starts a new round. One model runs at a time.";
  $("play-label").textContent = running ? "Pause" : game?.moves ? "Resume game" : "Start game";
  $("play-icon").textContent = running ? "Ⅱ" : "▶";
  $("control-note").textContent = pending && !running
    ? "Waiting for the current decision before pausing."
    : "Strands Decider chooses every move. Use Step for one decision or Start game for continued play.";
  $("game-status").textContent = !ready ? "Getting ready" : !active ? "Round complete"
    : pending ? "Deciding…" : running ? "Playing" : game?.moves ? "Paused" : "Ready to play";
  $("model-badge").className = `model-badge ${ready ? "ready" : model.status === "error" ? "failed" : ""}`;
  $("model-label").textContent = ready ? "Model online" : model.status === "error" ? "Model unavailable" : "Loading model";
  if (model.device) {
    $("model-device").textContent = `Local inference · ${model.device === "auto" ? "preparing device" : model.device.toUpperCase()}`;
  }
  if (model.model) {
    $("model-name").textContent = model.models?.find((item) => item.id === model.model)?.label || "Startup model";
    $("model-link").hidden = !model.model.startsWith("StrandsAgents/");
    $("model-link").href = `https://huggingface.co/${model.model.split("/").map(encodeURIComponent).join("/")}`;
  }
  if (model.status === "error") {
    setMessage("Model unavailable", "The model could not load", "Read the error message in the decision panel.", true);
  } else if (!ready) {
    setMessage("Getting started", "Loading the model", "Model files download on first use.");
  } else if (game?.status === "lost" || game?.status === "won") {
    setMessage(game.status === "won" ? "Board complete" : "Round ended",
      game.status === "won" ? "The snake filled the board." : game.message.replace("a body", "its own body"),
      "Select Reset to start a new game.", true);
  } else if (!game?.moves && !running && !pending) {
    setMessage("Ready to play", "Start a game", "Select Start game for continued play or Step for one move.");
  } else {
    setMessage("", "", "");
  }
  if (!game) return;
  $("score").textContent = String(game.score).padStart(2, "0");
  $("moves").textContent = String(game.moves).padStart(3, "0");
  $("length").textContent = String(game.snake.length).padStart(2, "0");
  $("foodless").textContent = game.moves_since_food ?? 0;
  $("revisits").textContent = game.head_revisits ?? 0;
  drawBoard();
  $("choice-arrow").textContent = decision ? arrows[decision.choice] : "↗";
  $("choice").textContent = decision ? names[decision.choice] : "Waiting to play";
  $("choice-label").textContent = decision ? "Model chose" : "Next direction";
  $("choice-detail").textContent = pending ? "Evaluating the next board…"
    : decision ? `Decision ${String(decision.move).padStart(3, "0")} · ${decision.input_tokens} input tokens`
    : "Select Step or Start game to begin.";
  $("decision-number").textContent = decision ? `# ${String(decision.move).padStart(3, "0")}` : "No decision yet";
  for (const row of document.querySelectorAll(".probability-row")) {
    const probability = decision?.probabilities[row.dataset.direction];
    row.classList.toggle("selected", decision?.choice === row.dataset.direction);
    row.querySelector(".bar-fill").style.width = `${(probability || 0) * 100}%`;
    row.querySelector(".probability").textContent = probability === undefined ? "N/A" : `${Math.round(probability * 100)}%`;
  }
  // Keep the unit markup fixed; model output is only ever inserted as text.
  $("confidence").firstChild.textContent = decision ? Math.round(decision.confidence * 100) : "N/A";
  $("latency").firstChild.textContent = decision ? decision.latency_ms.toLocaleString() : "N/A";
  $("confidence").querySelector("small").hidden = !decision;
  $("latency").querySelector("small").hidden = !decision;
  $("observation").textContent = decision?.observation ||
    "The board state sent for the latest decision will appear here.";
  $("history").replaceChildren();
  if (!history.length) {
    const empty = document.createElement("span");
    empty.className = "history-empty";
    empty.textContent = "No moves yet.";
    $("history").append(empty);
  }
  history.forEach((item) => {
    const chip = document.createElement("span");
    chip.className = "history-item";
    chip.textContent = arrows[item.choice];
    chip.title = `Move ${item.move}: ${names[item.choice]}`;
    chip.setAttribute("aria-label", chip.title);
    $("history").append(chip);
  });
}

function stop() {
  running = false;
  clearTimeout(timer);
  render();
}

async function takeStep() {
  if (pending || resetting || changingModel || model.status !== "ready" || !game || game.status !== "active") return;
  const turnGeneration = generation;
  pending = true;
  showError();
  render();
  try {
    const snapshot = await api("/api/step", { game_id: game.id, moves: game.moves });
    if (turnGeneration !== generation) return;
    model.busy = false;
    acceptSnapshot(snapshot);
    if (game.status !== "active") running = false;
  } catch (error) {
    if (turnGeneration !== generation) return;
    running = false;
    showError(error.message);
    // Reconcile after a stale tab or lost response; never retry a move automatically.
    try {
      const snapshot = await api("/api/game");
      if (turnGeneration === generation) acceptSnapshot(snapshot);
    } catch { /* Keep the last known board. */ }
  } finally {
    pending = false;
    render();
    if (running && turnGeneration === generation) {
      timer = setTimeout(takeStep, Number($("pace").value));
    }
  }
}

$("play").addEventListener("click", () => {
  if (running) return stop();
  running = true;
  showError();
  render();
  takeStep();
});
$("step").addEventListener("click", takeStep);
$("model-select").addEventListener("change", render);
$("load-model").addEventListener("click", async () => {
  stop();
  changingModel = true;
  generation += 1;
  showError();
  render();
  try {
    acceptSnapshot(await api("/api/model", { model: $("model-select").value }));
    setModel(await api("/api/status"));
  } catch (error) {
    showError(error.message);
    // A lost response may still have started a load. Read state before allowing more work.
    try {
      setModel(await api("/api/status"));
      acceptSnapshot(await api("/api/game"));
    } catch { /* The next status poll will report the server connection. */ }
  } finally {
    changingModel = false;
    render();
  }
});
$("reset").addEventListener("click", async () => {
  stop();
  resetting = true;
  generation += 1; // Ignore old browser responses as well as stale server decisions.
  showError();
  render();
  try {
    acceptSnapshot(await api("/api/reset", {}));
    history = [];
  } catch (error) {
    showError(error.message);
  } finally {
    resetting = false;
    render();
  }
});
$("pace").addEventListener("input", () => {
  $("pace-value").textContent = `${(Number($("pace").value) / 1000).toFixed(1)}s`;
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) stop(); // Do not keep spending compute in a hidden tab.
});

async function pollModel() {
  const pollGeneration = generation;
  try {
    const nextModel = await api("/api/status");
    if (pollGeneration !== generation || changingModel) return;
    if (model.status === "error" && nextModel.status === "ready") showError();
    const changed = (model.model && model.model !== nextModel.model)
      || (game && nextModel.game_id !== game.id);
    setModel(nextModel);
    if (changed) {
      stop();
      generation += 1;
      const refreshGeneration = generation;
      const snapshot = await api("/api/game");
      if (refreshGeneration !== generation || changingModel) return;
      acceptSnapshot(snapshot);
    }
    if (model.error) showError(model.error);
    if (model.status !== "ready") running = false;
    render();
  } catch {
    if (pollGeneration !== generation || changingModel) return;
    stop();
    model = { ...model, status: "error", busy: false };
    showError("The local server is unavailable. Run this in a terminal: uv run --locked python app.py");
    render();
  } finally {
    setTimeout(pollModel, 2000);
  }
}

async function initialize() {
  try { acceptSnapshot(await api("/api/game")); }
  catch { showError("Could not load the game. Check the local server, then refresh."); }
  pollModel();
}
initialize();
