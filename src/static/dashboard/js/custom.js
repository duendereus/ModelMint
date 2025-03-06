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

    // ✅ Initialize DataTables for each table metric separately with horizontal scrolling
    $('.table-metric').each(function() {
        let tableId = $(this).attr('id');  
        $('#' + tableId).DataTable({
            "paging": true,   
            "ordering": true,
            "searching": true,
            "info": false,
            "pageLength": 5,  
            "scrollX": true,  // ✅ Keep horizontal scroll inside the card
            "autoWidth": false, 
            "fixedHeader": true
        });
    });
});






