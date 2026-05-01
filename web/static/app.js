// app.js — Frontend helper scripts

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Lucide icons
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }

  // Show image preview thumbnail on file selection
  const fileInputs = document.querySelectorAll("input[type=file][accept='image/*']");
  fileInputs.forEach(input => {
    input.addEventListener("change", () => {
      const file = input.files[0];
      if (!file) return;

      // Update label text
      const label = input.closest(".form-group")?.querySelector("label");
      if (label) {
        const baseLabelText = label.dataset.originalLabel || label.textContent;
        label.dataset.originalLabel = baseLabelText.split(' — ')[0];
        label.textContent = `${label.dataset.originalLabel} — ${file.name}`;
        // Re-run lucide after label text change (icons may be cleared)
        if (typeof lucide !== 'undefined') lucide.createIcons();
      }

      // Show image preview
      const group = input.closest(".form-group");
      if (!group) return;
      let preview = group.querySelector(".file-preview");
      if (!preview) {
        preview = document.createElement("div");
        preview.className = "file-preview";
        preview.innerHTML = '<img alt="Preview">';
        input.after(preview);
      }
      const img = preview.querySelector("img");
      img.src = URL.createObjectURL(file);
      preview.style.display = "block";
    });
  });

  // ── Verify badge: click to toggle detail panel ─────────
  const verifyBadge = document.getElementById("verifyBadge");
  const verifyPanel = document.getElementById("verifyDetailPanel");
  if (verifyBadge && verifyPanel) {
    // Start with panel visible
    verifyPanel.style.display = "block";
    verifyBadge.addEventListener("click", () => {
      const shown = verifyPanel.style.display !== "none";
      verifyPanel.style.display = shown ? "none" : "block";
    });
  }

  // ── Endorse gallery ────────────────────────────────────
  const gallery = document.getElementById("captureGallery");
  const searchInput = document.getElementById("gallerySearch");
  const endorseInput = document.getElementById("endorseTxId");

  if (gallery) {
    let allCaptures = [];

    function renderGallery(captures) {
      if (captures.length === 0) {
        gallery.innerHTML = "";
        return;
      }
      gallery.innerHTML = captures.map(c => {
        const imgHtml = c.image_file
          ? `<img src="/uploads/${encodeURIComponent(c.image_file)}" alt="capture" loading="lazy">`
          : `<div class="gallery-item-no-img"><i data-lucide="image-off"></i></div>`;
        const device = c.device_name || "Unknown Device";
        const txShort = c.tx_id ? c.tx_id.slice(0, 12) + "…" : "—";
        return `<div class="gallery-item" data-txid="${c.tx_id || ''}" data-device="${device}">
          ${imgHtml}
          <div class="gallery-item-info">
            <div class="gallery-item-device">${device}</div>
            <div class="gallery-item-tx">${txShort}</div>
          </div>
        </div>`;
      }).join("");

      if (typeof lucide !== 'undefined') lucide.createIcons();

      // Click to select
      gallery.querySelectorAll(".gallery-item").forEach(item => {
        item.addEventListener("click", () => {
          gallery.querySelectorAll(".gallery-item").forEach(i => i.classList.remove("selected"));
          item.classList.add("selected");
          if (endorseInput && !endorseInput.readOnly) {
            endorseInput.value = item.dataset.txid;
          }
        });
      });
    }

    function filterGallery(query) {
      if (!query) return renderGallery(allCaptures);
      const q = query.toLowerCase();
      renderGallery(allCaptures.filter(c =>
        (c.tx_id || "").toLowerCase().includes(q) ||
        (c.device_name || "").toLowerCase().includes(q)
      ));
    }

    fetch("/api/captures")
      .then(r => r.json())
      .then(data => {
        allCaptures = data;
        renderGallery(allCaptures);
      })
      .catch(() => {
        gallery.innerHTML = '<div class="gallery-loading">Could not load captures.</div>';
      });

    if (searchInput) {
      searchInput.addEventListener("input", () => filterGallery(searchInput.value.trim()));
    }
  }
});
