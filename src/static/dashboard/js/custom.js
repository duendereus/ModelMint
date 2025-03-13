document.addEventListener("DOMContentLoaded", function () {
    let alerts = document.querySelectorAll(".alert");

    alerts.forEach((alert) => {
        // Show animation
        setTimeout(() => {
            alert.classList.add("show-notification");
        }, 100);

        // Auto-close after 5 seconds
        setTimeout(() => {
            closeAlert(alert);
        }, 4000);
    });

    // Event delegation for close button
    document.addEventListener("click", function (event) {
        if (event.target.classList.contains("close")) {
            let alert = event.target.closest(".alert");
            closeAlert(alert);
        }
    });

    // Function to close alerts with animation
    function closeAlert(alert) {
        if (alert) {
            alert.style.opacity = "0";
            setTimeout(() => {
                alert.remove();
            }, 500);
        }
    }
});

// ✅ Fix DataTables Initialization Issue
$(document).ready(function() {
    console.log("✅ Custom.js Loaded");

    $('.table-metric').each(function() {
        let tableId = $(this).attr('id');

        // ✅ Check if DataTable is already initialized
        if ($.fn.DataTable.isDataTable('#' + tableId)) {
            $('#' + tableId).DataTable().destroy();  // ✅ Destroy existing instance
        }

        // ✅ Reinitialize DataTable with proper configuration
        $('#' + tableId).DataTable({
            "paging": true,   
            "ordering": true,
            "searching": true,
            "info": false,
            "pageLength": 5,  
            "scrollX": true,  
            "autoWidth": false, 
            "fixedHeader": true
        });
    });
});







