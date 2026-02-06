document.addEventListener("DOMContentLoaded", () => {

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

});
