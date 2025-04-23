document.addEventListener("DOMContentLoaded", function () {

    // 1. Notification Alert Logic
    let alerts = document.querySelectorAll(".alert");

    alerts.forEach((alert) => {
        setTimeout(() => {
            alert.classList.add("show-notification");
        }, 100);

        setTimeout(() => {
            closeAlert(alert);
        }, 4000);
    });

    document.addEventListener("click", function (event) {
        if (event.target.classList.contains("close")) {
            let alert = event.target.closest(".alert");
            closeAlert(alert);
        }
    });

    function closeAlert(alert) {
        if (alert) {
            alert.style.opacity = "0";
            setTimeout(() => {
                alert.remove();
            }, 500);
        }
    }

    // 2. Initialize DataTables
    document.querySelectorAll('.table-metric').forEach((table) => {
        let tableId = table.id;

        if ($.fn.DataTable.isDataTable('#' + tableId)) {
            $('#' + tableId).DataTable().destroy();
        }

        $('#' + tableId).DataTable({
            paging: true,
            ordering: true,
            searching: true,
            info: false,
            pageLength: 5,
            scrollX: true,
            autoWidth: false,
            fixedHeader: true
        });
    });

    // 3. Plot image click logic (for Bootstrap Modal)
    document.querySelectorAll('.plot-thumbnail').forEach((img) => {
        img.addEventListener('click', function () {
            let imageUrl = this.getAttribute('data-image');
            if (imageUrl) {
                let modalImg = document.getElementById('modalPlotImage');
                modalImg.src = imageUrl;
            }
        });
    });
});

document.addEventListener("DOMContentLoaded", function () {
    const operationSelect = document.getElementById("id_operation");
    const datasetNameGroup = document.getElementById("dataset-name-group");
    const datasetDescriptionGroup = document.getElementById("dataset-description-group");
    const datasetDropdownGroup = document.getElementById("dataset-dropdown-group");
    const datasetDropdown = document.getElementById("id_dataset_id");

    function fetchDatasets() {
        fetch("/dashboard/analytics/get-datasets/")
            .then((res) => res.json())
            .then((data) => {
                datasetDropdown.innerHTML = ""; // Clear existing options

                if (data.datasets.length === 0) {
                    const option = document.createElement("option");
                    option.value = "";
                    option.textContent = "No datasets available";
                    datasetDropdown.appendChild(option);
                } else {
                    const defaultOption = document.createElement("option");
                    defaultOption.value = "";
                    defaultOption.textContent = "Select a dataset";
                    datasetDropdown.appendChild(defaultOption);

                    data.datasets.forEach((dataset) => {
                        const option = document.createElement("option");
                        option.value = dataset.id;
                        option.textContent = dataset.name;
                        datasetDropdown.appendChild(option);
                    });
                }
            })
            .catch((err) => {
                console.error("⚠️ Error fetching datasets:", err);
                datasetDropdown.innerHTML = "<option value=''>Error loading datasets</option>";
            });
    }

    function toggleDatasetInputs() {
        const selected = operationSelect.value;
    
        if (selected === "create") {
            datasetNameGroup.style.display = "block";
            datasetDescriptionGroup.style.display = "block";
            datasetDropdownGroup.style.display = "none";
    
            // Make only dataset_name required
            document.getElementById("id_dataset_name").required = true;
            document.getElementById("id_dataset_id").required = false;
    
        } else if (selected === "append" || selected === "replace") {
            datasetNameGroup.style.display = "none";
            datasetDescriptionGroup.style.display = "none";
            datasetDropdownGroup.style.display = "block";
    
            // Make only dataset_id required
            document.getElementById("id_dataset_name").required = false;
            document.getElementById("id_dataset_id").required = true;
    
            fetchDatasets();
        }
    }    

    if (operationSelect) {
        toggleDatasetInputs();  // Initial state on load
        operationSelect.addEventListener("change", toggleDatasetInputs);
    }
});




