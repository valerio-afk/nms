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

function initPermissionSwitches() {

    // find all forms with class form-perms
    const forms = document.querySelectorAll("form.form-perms");

    forms.forEach(form => {

        // helper to extract index from id
        function getIndexFromId(id, prefix) {
            return id.replace(prefix, "");
        }

        // ---------------------------------
        // HEADER SWITCH -> BODY SWITCHES
        // ---------------------------------
        form.querySelectorAll('[id^="switch--"]').forEach(headerSwitch => {

            headerSwitch.addEventListener("click", function (e) {
                e.stopPropagation();
            });

            headerSwitch.addEventListener("change", function (e) {

                const idx = getIndexFromId(this.id, "switch--");

                const container = form.querySelector(`#perm-dom-${idx}`);
                if (!container) return;

                const bodySwitches = container.querySelectorAll('input[type="checkbox"]');

                bodySwitches.forEach(sw => {
                    sw.checked = this.checked;
                });

                e.stopPropagation();

            });

        });

        // ---------------------------------
        // BODY SWITCHES -> HEADER SWITCH
        // ---------------------------------
        form.querySelectorAll('[id^="perm-dom-"] input[type="checkbox"]').forEach(bodySwitch => {

            bodySwitch.addEventListener("change", function () {

                // find parent container
                const container = this.closest('[id^="perm-dom-"]');
                if (!container) return;

                // extract index from container id
                const match = container.id.match(/^perm-dom-(\d+)/);
                if (!match) return;

                const idx = match[1];

                const headerSwitch = form.querySelector(`#switch--${idx}`);
                if (!headerSwitch) return;

                // get ALL switches inside this container
                const bodySwitches = container.querySelectorAll('input[type="checkbox"]');

                const allChecked = Array.from(bodySwitches)
                    .every(sw => sw.checked);

                headerSwitch.checked = allChecked;

            });

        });


    });
}

function initCopyToClipboard()
{
    const buttons = document.querySelectorAll(".copy-clipboard");
    const toastEl = document.getElementById("copyToast");
    const toast = new bootstrap.Toast(toastEl);

    buttons.forEach(button => {
        button.addEventListener("click", async () => {
            const targetId = button.getAttribute("data-target");
            const input = document.getElementById(targetId);

            if (!input) return;

            try {
                await navigator.clipboard.writeText(input.value);
                toast.show(); // show the Bootstrap toast
            } catch (err) {
                console.error("Failed to copy: ", err);
            }

            // fallback

            input.select();
            input.setSelectionRange(0, 99999); // For mobile devices
            const successful = document.execCommand("copy");

            if (successful) {
                toast.show();
            }
        });
    });
}

function eventChangeForm()
{
    document.querySelectorAll(".event-btn").forEach(button => {
    button.addEventListener("click", () => {
      const uuid = button.dataset.eventUuid;

      const div = document.querySelector(`.event-parameters[data-event-uuid="${uuid}"]`);
      const form = document.querySelector(`.event-form[data-event-uuid="${uuid}"]`);

      if (div) div.classList.add("d-none");
      if (form) form.classList.remove("d-none");
    });
  });
}

// Auto init
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeToggleControls);
    document.addEventListener('DOMContentLoaded', disableOnSubmit);
    document.addEventListener('DOMContentLoaded', enablePasswordToggle);
    document.addEventListener('DOMContentLoaded', initPermissionSwitches);
    document.addEventListener('DOMContentLoaded', eventChangeForm);
    document.addEventListener('DOMContentLoaded', initCopyToClipboard);
} else {
    initializeToggleControls()
    disableOnSubmit()
    enablePasswordToggle()
    initPermissionSwitches()
    eventChangeForm()
    initCopyToClipboard()
}




