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