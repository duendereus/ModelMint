window.addEventListener("load", function() {
    // Ocultar todos los tabs
    document.querySelectorAll("#pix-tabs-content .content").forEach(function(content) {
        content.style.display = "none";
    });

    // Activar solo el primer tab
    var firstTab = document.querySelector("#pix-tabs-content .content:nth-child(1)");
    if (firstTab) {
        firstTab.style.display = "block";
    }

    // Marcar el primer botón como activo
    document.querySelectorAll("#pix-tabs-nav li").forEach(function(tab) {
        tab.classList.remove("active");
    });
    var firstNav = document.querySelector("#pix-tabs-nav li:nth-child(1)");
    if (firstNav) {
        firstNav.classList.add("active");
    }
});

if (window.innerWidth > 768) {
    new WOW().init();
}
