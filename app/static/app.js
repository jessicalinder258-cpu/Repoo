const els = {
  composer: document.getElementById("composer"),
  title: document.getElementById("title"),
  priority: document.getElementById("priority"),
  dueDate: document.getElementById("due-date"),
  error: document.getElementById("error"),
  filters: document.getElementById("filters"),
  clearCompleted: document.getElementById("clear-completed"),
  list: document.getElementById("tasks"),
  empty: document.getElementById("empty"),
  summary: document.getElementById("summary"),
  progress: document.getElementById("progress"),
  progressLabel: document.getElementById("progress-label"),
  template: document.getElementById("task-template"),
};

let currentFilter = "all";

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        message = body.detail[0].msg;
      }
    } catch {
      // Response had no JSON body; keep the generic message.
    }
    throw new Error(message);
  }

  return response.status === 204 ? null : response.json();
}

function showError(message) {
  els.error.textContent = message;
  els.error.hidden = !message;
}

function formatDue(value) {
  const due = new Date(`${value}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((due - today) / 86400000);

  if (days === 0) return { label: "Due today", overdue: false };
  if (days === 1) return { label: "Due tomorrow", overdue: false };
  if (days === -1) return { label: "1 day late", overdue: true };
  if (days < 0) return { label: `${Math.abs(days)} days late`, overdue: true };
  if (days <= 7) return { label: `Due in ${days} days`, overdue: false };

  return {
    label: due.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    overdue: false,
  };
}

function renderTask(task) {
  const node = els.template.content.firstElementChild.cloneNode(true);
  const toggle = node.querySelector(".toggle");
  const title = node.querySelector(".task-title");
  const priority = node.querySelector(".priority");
  const due = node.querySelector(".due");

  node.dataset.id = task.id;
  node.classList.toggle("done", task.completed);
  toggle.checked = task.completed;
  toggle.setAttribute("aria-label", `Mark "${task.title}" as done`);
  title.textContent = task.title;
  title.title = "Click to rename";
  node.querySelector(".task-notes").textContent = task.notes;

  priority.textContent = task.priority;
  priority.classList.add(task.priority);

  if (task.due_date) {
    const { label, overdue } = formatDue(task.due_date);
    due.textContent = label;
    due.classList.toggle("overdue", overdue && !task.completed);
  }

  toggle.addEventListener("change", () =>
    mutate(() =>
      api(`/api/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({ completed: toggle.checked }),
      }),
    ),
  );

  node.querySelector(".delete").addEventListener("click", () =>
    mutate(() => api(`/api/tasks/${task.id}`, { method: "DELETE" })),
  );

  title.addEventListener("click", () => startEditing(title, task));
  title.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      startEditing(title, task);
    }
  });

  return node;
}

function startEditing(titleEl, task) {
  if (titleEl.dataset.editing === "true") return;
  titleEl.dataset.editing = "true";

  const input = document.createElement("input");
  input.className = "task-title-input";
  input.value = task.title;
  input.maxLength = 200;

  // Enter and the blur it triggers would otherwise both try to close the editor.
  let closed = false;
  const finish = async (save) => {
    if (closed) return;
    closed = true;

    input.replaceWith(titleEl);
    titleEl.dataset.editing = "false";
    const value = input.value.trim();
    if (!save || !value || value === task.title) return;
    await mutate(() =>
      api(`/api/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({ title: value }),
      }),
    );
  };

  input.addEventListener("blur", () => finish(true));
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") finish(true);
    if (event.key === "Escape") finish(false);
  });

  titleEl.replaceWith(input);
  input.focus();
  input.select();
}

function renderStats(stats) {
  const { total, active, completed } = stats;
  els.summary.textContent = total
    ? `${active} active · ${completed} done · ${total} total`
    : "No tasks yet";

  const percent = total ? Math.round((completed / total) * 100) : 0;
  els.progress.style.setProperty("--value", `${percent}%`);
  els.progressLabel.textContent = `${percent}%`;
  els.clearCompleted.hidden = completed === 0;
}

async function refresh() {
  const [tasks, stats] = await Promise.all([
    api(`/api/tasks?status=${currentFilter}`),
    api("/api/stats"),
  ]);

  els.list.replaceChildren(...tasks.map(renderTask));
  els.empty.hidden = tasks.length > 0;
  els.empty.textContent =
    currentFilter === "all"
      ? "Nothing here yet. Add your first task."
      : `No ${currentFilter} tasks.`;

  renderStats(stats);
}

async function mutate(action) {
  try {
    showError("");
    await action();
    await refresh();
  } catch (error) {
    showError(error.message);
  }
}

els.composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = els.title.value.trim();
  if (!title) return;

  await mutate(async () => {
    await api("/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        title,
        priority: els.priority.value,
        due_date: els.dueDate.value || null,
      }),
    });
    els.composer.reset();
    els.title.focus();
  });
});

els.filters.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-filter]");
  if (!button) return;

  currentFilter = button.dataset.filter;
  for (const tab of els.filters.querySelectorAll("button[data-filter]")) {
    tab.classList.toggle("active", tab === button);
  }
  mutate(() => Promise.resolve());
});

els.clearCompleted.addEventListener("click", () =>
  mutate(() => api("/api/tasks/completed", { method: "DELETE" })),
);

refresh().catch((error) => showError(error.message));
