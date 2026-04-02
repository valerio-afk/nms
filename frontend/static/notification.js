function showToast(data)
{
    const container = document.getElementById("toast-container");

    const toastEl = document.createElement("div");
    toastEl.className = "toast";
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");

    toastEl.innerHTML = `
      <div class="toast-header">
        <strong class="me-auto">${data.title}</strong>
        <small class="text-muted ms-2">${data.time}</small>
        <button type="button" class="btn-close ms-2 mb-1" data-bs-dismiss="toast"></button>
      </div>
      <div class="toast-body">
        ${data.body}
      </div>
    `;

    container.appendChild(toastEl);

    // Initialise Bootstrap toast
    const toast = new bootstrap.Toast(toastEl, {
      autohide:false
    });

    toast.show();

    // Optional: remove from DOM after hidden
    toastEl.addEventListener("hidden.bs.toast", () => {
      toastEl.remove();
    });
}

