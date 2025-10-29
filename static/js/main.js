// ===============================
// MAIN.JS - Interactividad general
// ===============================

// Espera a que el DOM esté listo
document.addEventListener("DOMContentLoaded", function () {
  // Animación de aparición suave
  document.body.classList.add("fade-in");

  // Activar tooltips de Bootstrap
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  [...tooltipTriggerList].map(t => new bootstrap.Tooltip(t));

  // Resaltar enlace activo en navbar
  const currentPath = window.location.pathname;
  document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });

  // Scroll suave para enlaces internos
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault();
      document.querySelector(this.getAttribute('href')).scrollIntoView({
        behavior: 'smooth'
      });
    });
  });

  // Animación en tarjetas al pasar el mouse
  document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('mouseenter', () => card.classList.add('hover-card'));
    card.addEventListener('mouseleave', () => card.classList.remove('hover-card'));
  });

  // Loader opcional (si lo implementas en base.html)
  const loader = document.getElementById('loader');
  if (loader) {
    setTimeout(() => loader.style.display = 'none', 800);
  }
});

// ===============================
// Funciones utilitarias
// ===============================

// Muestra notificación (reutilizable con toast de Bootstrap)
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast align-items-center text-bg-${type} border-0 show`;
  toast.role = "alert";
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>`;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// Inicializar DataTables
$(document).ready(function() {
    if($('.datatable').length > 0) {
        $('.datatable').DataTable({
            language: {
                url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/es-ES.json'
            }
        });
    }
});