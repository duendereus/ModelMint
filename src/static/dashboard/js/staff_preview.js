document.addEventListener("DOMContentLoaded", function () {
    const metricContainer = document.getElementById("metric-list");
    const form = document.getElementById("publish-form");
    const removedIds = new Set();

    // Función para inicializar CKEditor
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

    // Función para destruir CKEditor antes de mover
    function destroyCKEditors() {
        document.querySelectorAll(".ckeditor-field").forEach((el) => {
            if (el.ckeditorInstance) {
                el.ckeditorInstance.destroy()
                    .then(() => el.ckeditorInstance = null)
                    .catch(console.error);
            }
        });
    }

    // Habilitar drag-and-drop con limpieza y reinstancia de CKEditor
    Sortable.create(metricContainer, {
        animation: 150,
        handle: ".cursor-move",
        ghostClass: "bg-light",
        onStart: destroyCKEditors,
        onEnd: () => {
            setTimeout(() => {
                initializeCKEditors();
            }, 10);  // Pequeño delay para asegurar que el DOM se haya actualizado
        }
    });

    // Marcar métricas eliminadas
    metricContainer.querySelectorAll(".delete-metric").forEach((btn) => {
        btn.addEventListener("click", function () {
            const item = btn.closest(".metric-item");
            const metricId = item.dataset.id;
            removedIds.add(metricId);
            item.remove();
        });
    });

    // Inicialización inicial de CKEditor
    initializeCKEditors();

    // Manejar publicación del formulario
    form.addEventListener("submit", function (e) {
        e.preventDefault();

        const submitBtn = form.querySelector("button[type='submit']");
        const originalText = submitBtn.innerHTML;

        submitBtn.disabled = true;
        submitBtn.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            Publishing...
        `;

        const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;

        const orderedIds = [...document.querySelectorAll(".metric-item")]
            .map((el) => el.dataset.id)
            .filter((id) => !removedIds.has(id));

        const editedTitles = {};
        const editedValues = {};

        document.querySelectorAll(".editable-title").forEach((input) => {
            const original = input.dataset.original;
            const current = input.value;
            const id = input.dataset.id;
            if (original !== current) {
                editedTitles[id] = current;
            }
        });

        document.querySelectorAll(".editable-value").forEach((input) => {
            const id = input.dataset.id;
            let current = input.value;

            if (input.ckeditorInstance) {
                current = input.ckeditorInstance.getData();
            }

            editedValues[id] = current;
        });

        fetch(window.location.pathname, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
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
                submitBtn.innerHTML = originalText;
            }
        })
        .catch((err) => {
            console.error("Error:", err);
            alert("❌ Request failed.");
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        });
    });
});

