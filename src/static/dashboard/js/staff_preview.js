document.addEventListener("DOMContentLoaded", () => {
    const selectedUploadId = new URLSearchParams(window.location.search).get("upload_id");
    const metricContainer = document.getElementById("metric-list");
    const form = document.getElementById("publish-form");
    const removedIds = new Set();

    // 🔧 CKEditor helpers
    function initializeCKEditors() {
        document.querySelectorAll(".ckeditor-field").forEach((el) => {
            if (!el.ckeditorInstance) {
                ClassicEditor.create(el, {
                    toolbar: [
                        "heading", "|",
                        "bold", "italic", "link", "|",
                        "bulletedList", "numberedList", "|",
                        "undo", "redo"
                    ]
                }).then((editor) => {
                    el.ckeditorInstance = editor;
                }).catch(console.error);
            }
        });
    }

    function destroyCKEditors() {
        document.querySelectorAll(".ckeditor-field").forEach((el) => {
            if (el.ckeditorInstance) {
                el.ckeditorInstance.destroy()
                    .then(() => el.ckeditorInstance = null)
                    .catch(console.error);
            }
        });
    }

    // 🧱 Drag-and-drop config
    if (metricContainer) {
        Sortable.create(metricContainer, {
            animation: 150,
            handle: ".cursor-move",
            ghostClass: "bg-light",
            onStart: destroyCKEditors,
            onEnd: () => setTimeout(initializeCKEditors, 10)
        });

        metricContainer.querySelectorAll(".delete-metric").forEach((btn) => {
            btn.addEventListener("click", () => {
                const item = btn.closest(".metric-item");
                const id = item.dataset.id;
                removedIds.add(id);
                item.remove();
            });
        });
    }

    initializeCKEditors();

    // 📨 Submit handler
    form?.addEventListener("submit", (e) => {
        e.preventDefault();

        const submitBtn = form.querySelector("button[type='submit']");
        const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
        const originalHTML = submitBtn.innerHTML;

        submitBtn.disabled = true;
        submitBtn.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            Publishing...
        `;

        const orderedIds = [...document.querySelectorAll(".metric-item")]
            .map(el => el.dataset.id)
            .filter(id => !removedIds.has(id));

        const editedTitles = {};
        const editedValues = {};

        document.querySelectorAll(".editable-title").forEach((input) => {
            const id = input.dataset.id;
            const original = input.dataset.original;
            const current = input.value;
            if (original !== current) {
                editedTitles[id] = current;
            }
        });

        document.querySelectorAll(".editable-value").forEach((input) => {
            const id = input.dataset.id;
            const current = input.ckeditorInstance
                ? input.ckeditorInstance.getData()
                : input.value;
            editedValues[id] = current;
        });

        fetch(window.location.href, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                upload_id: selectedUploadId,
                ordered_ids: orderedIds,
                removed_ids: [...removedIds],
                edited_titles: editedTitles,
                edited_values: editedValues
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert("✅ Report published successfully!");
                window.location.href = data.redirect_url;
            } else {
                alert("❌ Error: " + (data.error || "Unknown error."));
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalHTML;
            }
        })
        .catch(err => {
            console.error("❌ Request failed:", err);
            alert("❌ Request failed.");
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHTML;
        });
    });
});
