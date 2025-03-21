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






