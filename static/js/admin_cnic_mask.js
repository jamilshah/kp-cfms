/**
 * Auto-format CNIC input fields in Django Admin
 */
document.addEventListener('DOMContentLoaded', function() {
    const cnicFields = document.querySelectorAll('input[name="cnic"]');
    
    cnicFields.forEach(function(input) {
        input.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, ''); // Remove non-digits
            if (value.length > 13) value = value.slice(0, 13);
            
            // Format: XXXXX-XXXXXXX-X
            if (value.length > 12) {
                value = value.slice(0, 5) + '-' + value.slice(5, 12) + '-' + value.slice(12);
            } else if (value.length > 5) {
                value = value.slice(0, 5) + '-' + value.slice(5);
            }
            
            e.target.value = value;
        });
    });
});
