// app.js — Frontend helper scripts

// Show selected filename next to file input label
document.addEventListener("DOMContentLoaded", () => {
  const fileInputs = document.querySelectorAll("input[type=file][accept='image/*']");
  fileInputs.forEach(input => {
    input.addEventListener("change", () => {
      const file = input.files[0];
      if (!file) return;
      const label = input.closest(".form-group")?.querySelector("label");
      if (label) label.textContent += ` — ${file.name}`;
    });
  });
});
