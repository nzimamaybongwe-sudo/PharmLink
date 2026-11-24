/* PharmLink - Main JavaScript */
'use strict';

// ── Sidebar Toggle ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.querySelector('.main-content');

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function () {
            if (window.innerWidth <= 768) {
                sidebar.classList.toggle('open');
            } else {
                sidebar.classList.toggle('collapsed');
                if (sidebar.classList.contains('collapsed')) {
                    sidebar.style.width = '64px';
                    if (mainContent) mainContent.style.marginLeft = '64px';
                    document.querySelectorAll('.sidebar-menu .nav-link span, .brand-text, .user-info, .sidebar-category, .sidebar-footer .nav-link span')
                        .forEach(el => el.style.display = 'none');
                } else {
                    sidebar.style.width = '260px';
                    if (mainContent) mainContent.style.marginLeft = '260px';
                    document.querySelectorAll('.sidebar-menu .nav-link span, .brand-text, .user-info, .sidebar-category, .sidebar-footer .nav-link span')
                        .forEach(el => el.style.display = '');
                }
            }
        });
    }

    // ── Auto-dismiss alerts after 5 seconds ──────────────────────────────
    document.querySelectorAll('.alert:not(.alert-permanent)').forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 6000);
    });

    // ── Confirm dialogs ──────────────────────────────────────────────────
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            const msg = this.dataset.confirm || 'Are you sure?';
            if (!confirm(msg)) {
                e.preventDefault();
                return false;
            }
        });
    });

    // ── Form submitting state ────────────────────────────────────────────
    document.querySelectorAll('form[data-loading]').forEach(function (form) {
        form.addEventListener('submit', function () {
            const btn = form.querySelector('[type="submit"]');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Processing...';
            }
        });
    });

    // ── Tooltips ────────────────────────────────────────────────────────
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el);
    });

    // ── Popover ─────────────────────────────────────────────────────────
    document.querySelectorAll('[data-bs-toggle="popover"]').forEach(function (el) {
        new bootstrap.Popover(el);
    });

    // ── Dynamic prescription medicine rows ──────────────────────────────
    const addMedicineBtn = document.getElementById('addMedicineRow');
    if (addMedicineBtn) {
        addMedicineBtn.addEventListener('click', addMedicineRow);
    }

    // ── AJAX patient search in prescription form ─────────────────────────
    const patientSearch = document.getElementById('patientSearchInput');
    if (patientSearch) {
        let timeout;
        patientSearch.addEventListener('input', function () {
            clearTimeout(timeout);
            const q = this.value.trim();
            if (q.length < 2) return;
            timeout = setTimeout(() => {
                fetch(`/prescriptions/api/search-patient?q=${encodeURIComponent(q)}`)
                    .then(r => r.json())
                    .then(data => {
                        const list = document.getElementById('patientSearchResults');
                        if (!list) return;
                        list.innerHTML = '';
                        data.forEach(p => {
                            const item = document.createElement('button');
                            item.type = 'button';
                            item.className = 'list-group-item list-group-item-action';
                            item.innerHTML = `<strong>${p.name}</strong> <span class="text-muted">${p.number}</span>`;
                            item.addEventListener('click', () => {
                                document.getElementById('patientId').value = p.id;
                                document.getElementById('patientDisplay').textContent = `${p.name} (${p.number})`;
                                list.innerHTML = '';
                                patientSearch.value = `${p.name} (${p.number})`;
                            });
                            list.appendChild(item);
                        });
                    });
            }, 300);
        });
    }
});


// ── Add medicine row to prescription form ───────────────────────────────────
let medicineRowCount = 1;

function addMedicineRow() {
    const container = document.getElementById('medicineRows');
    if (!container) return;
    
    // Clone first row template
    const template = document.getElementById('medicineRowTemplate');
    if (!template) return;
    
    const newRow = template.cloneNode(true);
    newRow.id = '';
    newRow.style.display = '';
    newRow.classList.remove('d-none');
    
    // Clear values
    newRow.querySelectorAll('input, select, textarea').forEach(el => { el.value = ''; });
    
    // Update remove button
    const removeBtn = newRow.querySelector('.remove-medicine-row');
    if (removeBtn) {
        removeBtn.addEventListener('click', function () {
            newRow.remove();
        });
    }
    
    container.appendChild(newRow);
    medicineRowCount++;
}


// ── Chart helpers ────────────────────────────────────────────────────────────
function createDoughnutChart(canvasId, labels, data, colors) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{ data: data, backgroundColor: colors, borderWidth: 2, borderColor: '#fff' }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 15 } }
            },
            cutout: '70%'
        }
    });
}

function createBarChart(canvasId, labels, datasets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    return new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true,
            plugins: { legend: { display: datasets.length > 1 } },
            scales: {
                y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
                x: { grid: { display: false } }
            }
        }
    });
}

function createLineChart(canvasId, labels, datasets) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    return new Chart(ctx, {
        type: 'line',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true,
            plugins: { legend: { display: datasets.length > 1 } },
            scales: {
                y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
                x: { grid: { display: false } }
            },
            elements: { line: { tension: 0.4 } }
        }
    });
}

