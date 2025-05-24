document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.sidebar');
    const main = document.querySelector('.main');
    
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            main.classList.toggle('active');
        });
    }
    
    // Active menu item
    const currentPath = window.location.pathname;
    const menuItems = document.querySelectorAll('.sidebar a');
    
    menuItems.forEach(item => {
        if (item.getAttribute('href') === currentPath) {
            item.classList.add('active');
            
            // Expand parent if in submenu
            const parentCollapse = item.closest('.collapse');
            if (parentCollapse) {
                parentCollapse.classList.add('show');
                const parentLink = document.querySelector(`[href="#${parentCollapse.id}"]`);
                if (parentLink) {
                    parentLink.classList.add('active');
                }
            }
        }
    });
    
    // File input preview
    document.querySelectorAll('.file-input').forEach(input => {
        input.addEventListener('change', function() {
            const previewId = this.getAttribute('data-preview');
            const previewElement = document.getElementById(previewId);
            
            if (this.files && this.files[0]) {
                const reader = new FileReader();
                
                reader.onload = function(e) {
                    if (previewElement) {
                        previewElement.src = e.target.result;
                        previewElement.style.display = 'block';
                    }
                }
                
                reader.readAsDataURL(this.files[0]);
            }
        });
    });
});