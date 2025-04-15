document.addEventListener("DOMContentLoaded", function () {
    const MAX_SIZE_BYTES = 50 * 1024 * 1024;  // 50MB
    const CHUNK_SIZE = 5 * 1024 * 1024;       // 5MB

    const form = document.getElementById("upload-form");
    const fileInput = document.getElementById("id_file");
    const titleInput = document.getElementById("id_title");
    const instructionsInput = document.getElementById("id_job_instructions");
    const submitBtn = document.getElementById("submit-btn");

    const widget = document.getElementById("upload-widget");
    const progressBar = document.getElementById("upload-progress-bar");
    const statusText = document.getElementById("upload-status-text");

    // ✅ Comentado para evitar confusión con botón de cerrar el widget
    /*
    window.hideUploadWidget = function () {
        widget.style.display = "none";
    };
    */

    form.addEventListener("submit", async function (e) {
        e.preventDefault();

        const file = fileInput.files[0];
        const title = titleInput.value;
        const instructions = instructionsInput.value;

        if (!file || !title) {
            alert("⚠️ Please provide a title and select a file.");
            return;
        }

        showUploadWidget("Starting upload...");
        submitBtn.disabled = true;
        submitBtn.innerText = "Uploading...";

        if (file.size > MAX_SIZE_BYTES) {
            const warningModal = new bootstrap.Modal(document.getElementById("upload-warning-popup"));
            warningModal.show();

            setTimeout(() => {
                uploadLargeFile(file, title, instructions);
            }, 500);
        } else {
            await uploadSmallFile(file, title, instructions);
        }
    });

    async function uploadSmallFile(file, title, instructions) {
        const cleanFileName = file.name.replace(/\s+/g, "_");
        const presignForm = new FormData();
        presignForm.append("file_name", cleanFileName);

        const res = await fetch("/dashboard/analytics/upload/generate-url/", {
            method: "POST",
            headers: { "X-CSRFToken": getCSRFToken() },
            body: presignForm
        });

        const { data, file_key, error } = await res.json();
        if (error) {
            alert("❌ Failed to get upload URL");
            reset();
            return;
        }

        const s3FormData = new FormData();
        Object.entries(data.fields).forEach(([k, v]) => s3FormData.append(k, v));
        s3FormData.append("file", file);

        const xhr = new XMLHttpRequest();
        xhr.open("POST", data.url, true);

        xhr.upload.onprogress = function (e) {
            if (e.lengthComputable) updateProgress((e.loaded / e.total) * 100);
        };

        xhr.onload = async function () {
            if (xhr.status === 204 || xhr.status === 201) {
                await confirmUpload(file_key, title, instructions);
            } else {
                alert("❌ Upload failed.");
                reset();
            }
        };

        xhr.send(s3FormData);
    }

    async function uploadLargeFile(file, title, instructions) {
        const cleanFileName = file.name.replace(/\s+/g, "_");
        const initForm = new FormData();
        initForm.append("file_name", cleanFileName);
        initForm.append("content_type", file.type);

        const initRes = await fetch("/dashboard/analytics/upload/initiate-multipart-upload/", {
            method: "POST",
            headers: { "X-CSRFToken": getCSRFToken() },
            body: initForm
        });

        const { uploadId, key, error } = await initRes.json();
        if (error) {
            alert("❌ Could not initiate upload");
            reset();
            return;
        }

        const partCount = Math.ceil(file.size / CHUNK_SIZE);
        const parts = [];

        for (let i = 0; i < partCount; i++) {
            const start = i * CHUNK_SIZE;
            const end = Math.min(start + CHUNK_SIZE, file.size);
            const chunk = file.slice(start, end);
            const partNumber = i + 1;

            const urlRes = await fetch("/dashboard/analytics/upload/generate-part-url/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRFToken()
                },
                body: JSON.stringify({ key, uploadId, partNumber })
            });

            const { url } = await urlRes.json();

            const putRes = await fetch(url, { method: "PUT", body: chunk });
            if (!putRes.ok) {
                alert(`❌ Error uploading part ${partNumber}`);
                reset();
                return;
            }

            const etag = putRes.headers.get("ETag");
            parts.push({ ETag: etag.replace(/"/g, ""), PartNumber: partNumber });
            updateProgress(((i + 1) / partCount) * 100);
        }

        const completeRes = await fetch("/dashboard/analytics/upload/complete-multipart-upload/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken()
            },
            body: JSON.stringify({
                uploadId,
                key,
                parts,
                title,
                job_instructions: instructions
            })
        });

        const result = await completeRes.json();
        if (result.success) {
            updateStatusText("✅ Upload complete!");
            setTimeout(() => window.location.href = "/dashboard/", 1200);
        } else {
            if (result.redirect_url) {
                window.location.href = result.redirect_url;
            } else {
                alert("❌ Failed to complete multipart upload.");
                reset();
            }
        }

    }

    async function confirmUpload(file_key, title, instructions) {
        const confirmForm = new FormData();
        confirmForm.append("title", title);
        confirmForm.append("job_instructions", instructions);
        confirmForm.append("file_key", file_key);

        const res = await fetch("/dashboard/analytics/upload/confirm/", {
            method: "POST",
            headers: { "X-CSRFToken": getCSRFToken() },
            body: confirmForm
        });

        const result = await res.json();
        if (result.success) {
            updateStatusText("✅ Upload complete!");
            setTimeout(() => window.location.href = "/dashboard/", 1200);
        } else {
            if (result.redirect_url) {
                window.location.href = result.redirect_url;
            } else {
                alert("❌ Confirmation failed.");
                reset();
            }
        }
    }

    function updateProgress(percent) {
        progressBar.style.width = `${percent}%`;
        progressBar.innerText = `${Math.round(percent)}%`;
    }

    function updateStatusText(text) {
        statusText.innerText = text;
    }

    function showUploadWidget(initialText) {
        widget.style.display = "block";
        updateStatusText(initialText);
        updateProgress(0);
    }

    function reset() {
        submitBtn.disabled = false;
        submitBtn.innerText = "Submit";
        updateStatusText("Upload canceled or failed.");
    }

    function getCSRFToken() {
        return document.querySelector("[name=csrfmiddlewaretoken]").value;
    }
});
