document.addEventListener("DOMContentLoaded", function () {
    const MAX_SIZE_BYTES = 50 * 1024 * 1024;  // 50MB
    const CHUNK_SIZE = 5 * 1024 * 1024;       // 5MB

    const form = document.getElementById("upload-form");
    const fileInput = document.getElementById("id_file");
    const driveLinkInput = document.getElementById("id_drive_link");
    const titleInput = document.getElementById("id_title");
    const instructionsInput = document.getElementById("id_job_instructions");
    const submitBtn = document.getElementById("submit-btn");

    const widget = document.getElementById("upload-widget");
    const progressBar = document.getElementById("upload-progress-bar");
    const statusText = document.getElementById("upload-status-text");

    form.addEventListener("submit", async function (e) {
        e.preventDefault();
        console.log("🚀 Form submitted");

        const file = fileInput.files[0];
        const driveLink = driveLinkInput.value.trim();
        const title = titleInput.value.trim();
        const instructions = instructionsInput.value.trim();




        if (!title || (!file && !driveLink)) {
            alert("⚠️ Please provide a title and either select a file or paste a drive link.");
            console.log("⚠️ Missing file or drive link or title");
            return;
        }

        if (driveLink) {
            console.log("🌐 Drive link detected, skipping file upload.");
            await confirmUpload(null, title, instructions, driveLink);
            return;
        }

        console.log("📂 File selected:", file.name);
        console.log("📝 Title:", title);
        console.log("🛠️ Instructions:", instructions);

        showUploadWidget("Starting upload...");
        submitBtn.disabled = true;
        submitBtn.innerText = "Uploading...";

        if (file.size > MAX_SIZE_BYTES) {
            console.log("📦 Large file, using multipart upload");
            const warningModal = new bootstrap.Modal(document.getElementById("upload-warning-popup"));
            warningModal.show();

            setTimeout(() => {
                uploadLargeFile(file, title, instructions);
            }, 500);
        } else {
            console.log("📦 Small file, using direct POST upload");
            await uploadSmallFile(file, title, instructions);
        }
    });

    async function uploadSmallFile(file, title, instructions) {
        console.log("🔹 Starting small file upload:", file.name, file.size);
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
                await confirmUpload(file_key, title, instructions, null);
            } else {
                alert("❌ Upload failed.");
                reset();
            }
        };

        xhr.onerror = function () {
            console.error("❌ XMLHttpRequest failed:", xhr.status, xhr.statusText);
            alert("❌ Upload failed due to network error.");
            reset();
        };

        xhr.send(s3FormData);
    }

    async function uploadLargeFile(file, title, instructions) {
        console.log("🔸 Starting large file upload:", file.name, file.size);
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

    async function confirmUpload(file_key, title, instructions, drive_link) {
        const operation = document.getElementById("id_operation").value;

        const confirmForm = new FormData();
        confirmForm.append("title", title);
        confirmForm.append("job_instructions", instructions);
        confirmForm.append("operation", operation);

        if (file_key) {
            confirmForm.append("file_key", file_key);
        }
        if (drive_link) {
            confirmForm.append("drive_link", drive_link);
        }

        if (operation === "create") {
            const datasetName = document.getElementById("id_dataset_name").value;
            const datasetDesc = document.getElementById("id_dataset_description").value;
            confirmForm.append("dataset_name", datasetName);
            confirmForm.append("dataset_description", datasetDesc);
        } else {
            const datasetId = document.getElementById("id_dataset_id").value;
            confirmForm.append("dataset_id", datasetId);
        }

        try {
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
        } catch (err) {
            alert("❌ Network error. Please try again.");
            reset();
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
        if (!widget || !progressBar || !statusText) return;
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


