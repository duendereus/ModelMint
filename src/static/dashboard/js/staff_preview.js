document.addEventListener("DOMContentLoaded", function () {
    const metricContainer = document.getElementById("metric-list");
    const form = document.getElementById("publish-form");
    const removedIds = new Set();

    // Enable drag-and-drop reordering
    Sortable.create(metricContainer, {
        animation: 150,
        handle: ".cursor-move",
        ghostClass: "bg-light",
    });

    // Attach delete buttons
    metricContainer.querySelectorAll(".delete-metric").forEach((btn) => {
        btn.addEventListener("click", function () {
            const item = btn.closest(".metric-item");
            const metricId = item.dataset.id;
            removedIds.add(metricId);
            item.remove();
        });
    });

    // Submit the form with spinner and button lock
    form.addEventListener("submit", function (e) {
        e.preventDefault();

        const submitBtn = form.querySelector("button[type='submit']");
        const originalText = submitBtn.innerHTML;

        // Lock the button and show spinner
        submitBtn.disabled = true;
        submitBtn.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
            Publishing...
        `;

        const csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;

        const orderedIds = [...document.querySelectorAll(".metric-item")]
            .map(el => el.dataset.id)
            .filter(id => !removedIds.has(id));

        fetch(window.location.pathname, {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                ordered_ids: orderedIds,
                removed_ids: [...removedIds]
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
        .catch(err => {
            console.error("Error:", err);
            alert("❌ Request failed.");
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        });
    });
});


