function disableOnSubmit () {

    document.querySelectorAll("form.disable-on-submit")
        .forEach(form => {

            let alreadySubmitting = false;

            form.addEventListener("submit", (e) => {

                // Prevent double submit
                if (alreadySubmitting) {
                    e.preventDefault();
                    return;
                }

                alreadySubmitting = true;

                // Disable AFTER browser has processed submission
                setTimeout(() => {
                    form.querySelectorAll(
                        'button[type="submit"], input[type="submit"]'
                    ).forEach(btn => btn.disabled = true);
                }, 0);

            });

        });

}

document.addEventListener("change", function (e) {
    if (e.target.classList.contains("auto-submit-switch")) {
        if (e.target.form) {
            e.target.form.submit();
        }
    }
});

function initializeToggleControls() {
  // Get all forms on the page
  const forms = document.querySelectorAll('form');

  forms.forEach(form => {
    // Get all toggle checkboxes within this form
    const toggles = form.querySelectorAll('.toggle');

    toggles.forEach(toggle => {
      // Add change event listener to each toggle
      toggle.addEventListener('change', function() {
        updateToggleTargets(this, form);
      });

      // Initialize state on page load
      updateToggleTargets(toggle, form);
    });
  });
}

function updateToggleTargets(toggleCheckbox, form) {
  const toggleId = toggleCheckbox.id;

  // Find all elements controlled by this toggle within the same form
  const targets = form.querySelectorAll(`.toggle-target.${toggleId}`);

  targets.forEach(target => {
    // Get all toggles that control this target within the same form
    const controllingToggles = getControllingToggles(target, form);

    // Determine if the target should be enabled
    const shouldEnable = shouldTargetBeEnabled(target, controllingToggles);

    // Update the target's disabled state
    target.disabled = !shouldEnable;
  });
}

function getControllingToggles(target, form) {
  const toggles = [];
  const classList = Array.from(target.classList);

  // Find all toggle IDs in the target's classes
  classList.forEach(className => {
    if (className !== 'toggle-target') {
      // Only look for toggles within the same form
      const toggle = form.querySelector(`#${className}`);
      if (toggle && toggle.classList.contains('toggle')) {
        toggles.push(toggle);
      }
    }
  });

  return toggles;
}

function shouldTargetBeEnabled(target, controllingToggles) {
  // All controlling toggles must agree to enable the target
  return controllingToggles.every(toggle => {
    const isReversed = toggle.classList.contains('toggle-reverse');
    const isChecked = toggle.checked;

    // Normal toggle: enabled when checked
    // Reversed toggle: enabled when unchecked
    return isReversed ? !isChecked : isChecked;
  });
}


function togglePasswordVisibility(event) {
    const button = event.currentTarget;
    const inputId = button.getAttribute('data-password-id');
    const passwordInput = document.getElementById(inputId);
    if (!passwordInput) return;

    const type = passwordInput.type === 'password' ? 'text' : 'password';
    passwordInput.type = type;

    button.innerHTML = type === 'password' ? '<i class="bi bi-eye"></i>️' : '<i class="bi bi-eye-slash"></i>';
  }

function enablePasswordToggle() {
    document.querySelectorAll('button[data-password-id]').forEach(button => {
     if (!button._passwordToggleAttached) {  // custom flag
      button.addEventListener('click', togglePasswordVisibility);
      button._passwordToggleAttached = true; // mark as added
    }
    });
  }

// Auto init
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeToggleControls);
    document.addEventListener('DOMContentLoaded', disableOnSubmit);
    document.addEventListener('DOMContentLoaded', enablePasswordToggle);
} else {
    initializeToggleControls();
    disableOnSubmit();
    enablePasswordToggle()
}




