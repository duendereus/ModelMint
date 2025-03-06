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

$(document).ready(function() {
    console.log("✅ Custom.js Loaded");

    // ✅ Initialize DataTables for each table metric with horizontal scrolling
    $('.table-metric').each(function() {
        let tableId = $(this).attr('id');  // Get unique ID
        $('#' + tableId).DataTable({
            "paging": true,   // Enable pagination
            "ordering": true, // Enable sorting
            "searching": true, // Enable search bar
            "info": false, // Hide info text
            "pageLength": 5,  // Show 5 entries per page by default
            "scrollX": true,   // ✅ Enable horizontal scrolling
            "autoWidth": false, // ✅ Prevents shrinking
            "fixedHeader": true // ✅ Keeps headers visible when scrolling
        });
    });
});






