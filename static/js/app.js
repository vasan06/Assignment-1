const root = document.documentElement;
const themeToggle = document.querySelector("[data-theme-toggle]");
const savedTheme = localStorage.getItem("theme");

if (savedTheme) {
  root.dataset.theme = savedTheme;
} else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
  root.dataset.theme = "dark";
}

themeToggle?.addEventListener("click", () => {
  const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
  root.dataset.theme = nextTheme;
  localStorage.setItem("theme", nextTheme);
});

const fileInput = document.querySelector("[data-file-input]");
const dropZone = document.querySelector("[data-drop-zone]");
const selectedFiles = document.querySelector("[data-selected-files]");

function formatBytes(size) {
  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return unitIndex === 0 ? `${value} ${units[unitIndex]}` : `${value.toFixed(1)} ${units[unitIndex]}`;
}

function renderSelectedFiles() {
  if (!selectedFiles || !fileInput) return;

  selectedFiles.innerHTML = "";
  Array.from(fileInput.files).forEach((file) => {
    const item = document.createElement("div");
    item.className = "selected-pill";
    item.innerHTML = `<span>${file.name}</span><strong>${formatBytes(file.size)}</strong>`;
    selectedFiles.appendChild(item);
  });
}

fileInput?.addEventListener("change", renderSelectedFiles);

["dragenter", "dragover"].forEach((eventName) => {
  dropZone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
  });
});

dropZone?.addEventListener("drop", (event) => {
  if (!fileInput || !event.dataTransfer?.files.length) return;
  fileInput.files = event.dataTransfer.files;
  renderSelectedFiles();
});

const fileSearch = document.querySelector("[data-file-search]");
const fileRows = Array.from(document.querySelectorAll("[data-file-row]"));
const resultCount = document.querySelector("[data-result-count]");
const emptySearch = document.querySelector("[data-empty-search]");

fileSearch?.addEventListener("input", () => {
  const query = fileSearch.value.trim().toLowerCase();
  let visibleCount = 0;

  fileRows.forEach((row) => {
    const matches = row.dataset.fileName.includes(query);
    row.classList.toggle("is-hidden", !matches);
    if (matches) visibleCount += 1;
  });

  if (resultCount) {
    resultCount.textContent = `${visibleCount} file${visibleCount === 1 ? "" : "s"} shown`;
  }

  emptySearch?.classList.toggle("is-hidden", visibleCount !== 0);
});

document.querySelectorAll("[data-delete-form]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    const fileName = form.closest("[data-file-row]")?.querySelector("h3")?.textContent || "this file";
    if (!window.confirm(`Delete ${fileName}?`)) {
      event.preventDefault();
    }
  });
});
