document.addEventListener("DOMContentLoaded", function () {
    let alerts = document.querySelectorAll(".alert");
    
    alerts.forEach((alert) => {
        // Show animation
        setTimeout(() => {
            alert.classList.add("show-notification");
        }, 100);

        // Auto-close after 5 seconds
        setTimeout(() => {
            alert.style.opacity = "0";
            setTimeout(() => {
                alert.remove();
            }, 500);
        }, 5000);

        // Close button action
        alert.querySelector(".close").addEventListener("click", function () {
            alert.style.opacity = "0";
            setTimeout(() => {
                alert.remove();
            }, 500);
        });
    });
});
