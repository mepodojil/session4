document.addEventListener("DOMContentLoaded", () => {
  const capabilitiesList = document.getElementById("capabilities-list");
  const capabilitySelect = document.getElementById("capability");
  const registerForm = document.getElementById("register-form");
  const messageDiv = document.getElementById("message");
  const authButton = document.getElementById("auth-button");
  const logoutButton = document.getElementById("logout-button");
  const userBadge = document.getElementById("user-badge");
  const loginModal = document.getElementById("login-modal");
  const loginForm = document.getElementById("login-form");
  const cancelLoginButton = document.getElementById("cancel-login");

  let authToken = localStorage.getItem("authToken") || "";
  let currentUser = null;

  function showMessage(text, kind) {
    messageDiv.textContent = text;
    messageDiv.className = kind;
    messageDiv.classList.remove("hidden");

    setTimeout(() => {
      messageDiv.classList.add("hidden");
    }, 5000);
  }

  function getAuthHeaders() {
    if (!authToken) {
      return {};
    }

    return {
      "X-Auth-Token": authToken,
    };
  }

  function isPracticeLead() {
    return currentUser && currentUser.role === "practice_lead";
  }

  function setAuthUiState() {
    if (isPracticeLead()) {
      authButton.textContent = "Switch Practice Lead";
      logoutButton.classList.remove("hidden");
      userBadge.textContent = `${currentUser.username} (${currentUser.role})`;
      userBadge.classList.remove("hidden");
    } else {
      authButton.textContent = "Practice Lead Login";
      logoutButton.classList.add("hidden");
      userBadge.classList.add("hidden");
      userBadge.textContent = "";
    }
  }

  function closeLoginModal() {
    loginModal.classList.add("hidden");
    loginForm.reset();
  }

  async function hydrateAuth() {
    if (!authToken) {
      currentUser = null;
      setAuthUiState();
      return;
    }

    try {
      const response = await fetch("/auth/me", {
        headers: getAuthHeaders(),
      });
      const result = await response.json();

      if (result.authenticated) {
        currentUser = result.user;
      } else {
        authToken = "";
        currentUser = null;
        localStorage.removeItem("authToken");
      }
    } catch (error) {
      currentUser = null;
      authToken = "";
      localStorage.removeItem("authToken");
      console.error("Error checking auth state:", error);
    }

    setAuthUiState();
  }

  // Function to fetch capabilities from API
  async function fetchCapabilities() {
    try {
      const response = await fetch("/capabilities");
      const capabilities = await response.json();

      // Clear loading message
      capabilitiesList.innerHTML = "";

      // Populate capabilities list
      Object.entries(capabilities).forEach(([name, details]) => {
        const capabilityCard = document.createElement("div");
        capabilityCard.className = "capability-card";

        const availableCapacity = details.capacity || 0;
        const currentConsultants = details.consultants ? details.consultants.length : 0;

        // Create consultants HTML with delete icons
        const consultantsHTML =
          details.consultants && details.consultants.length > 0
            ? `<div class="consultants-section">
              <h5>Registered Consultants:</h5>
              <ul class="consultants-list">
                ${details.consultants
                  .map(
                    (email) =>
                      `<li><span class="consultant-email">${email}</span>${
                        isPracticeLead()
                          ? `<button class="delete-btn" data-capability="${name}" data-email="${email}">Remove</button>`
                          : ""
                      }</li>`
                  )
                  .join("")}
              </ul>
            </div>`
            : `<p><em>No consultants registered yet</em></p>`;

        const pendingHTML =
          details.pending_requests && details.pending_requests.length > 0
            ? `<div class="pending-section">
              <h5>Pending Registration Requests:</h5>
              <ul class="pending-list">
                ${details.pending_requests
                  .map(
                    (request) =>
                      `<li>
                        <div>
                          <strong>${request.email}</strong>
                          <p class="pending-meta">Requested by ${request.requested_by}</p>
                        </div>
                        ${
                          isPracticeLead()
                            ? `<div class="pending-actions">
                                 <button class="approve-btn" data-capability="${name}" data-request-id="${request.id}">Approve</button>
                                 <button class="reject-btn" data-capability="${name}" data-request-id="${request.id}">Reject</button>
                               </div>`
                            : ""
                        }
                      </li>`
                  )
                  .join("")}
              </ul>
            </div>`
            : "";

        capabilityCard.innerHTML = `
          <h4>${name}</h4>
          <p>${details.description}</p>
          <p><strong>Practice Area:</strong> ${details.practice_area}</p>
          <p><strong>Industry Verticals:</strong> ${details.industry_verticals ? details.industry_verticals.join(', ') : 'Not specified'}</p>
          <p><strong>Capacity:</strong> ${availableCapacity} hours/week available</p>
          <p><strong>Current Team:</strong> ${currentConsultants} consultants</p>
          <div class="consultants-container">
            ${consultantsHTML}
          </div>
          ${pendingHTML}
        `;

        capabilitiesList.appendChild(capabilityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        capabilitySelect.appendChild(option);
      });

      // Add event listeners to delete buttons
      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });

      document.querySelectorAll(".approve-btn").forEach((button) => {
        button.addEventListener("click", handleApprove);
      });

      document.querySelectorAll(".reject-btn").forEach((button) => {
        button.addEventListener("click", handleReject);
      });
    } catch (error) {
      capabilitiesList.innerHTML =
        "<p>Failed to load capabilities. Please try again later.</p>";
      console.error("Error fetching capabilities:", error);
    }
  }

  async function handleApprove(event) {
    const button = event.target;
    const capability = button.getAttribute("data-capability");
    const requestId = button.getAttribute("data-request-id");

    try {
      const response = await fetch(
        `/capabilities/${encodeURIComponent(
          capability
        )}/approve?request_id=${encodeURIComponent(requestId)}`,
        {
          method: "POST",
          headers: getAuthHeaders(),
        }
      );

      const result = await response.json();
      if (response.ok) {
        showMessage(result.message, "success");
        fetchCapabilities();
      } else {
        showMessage(result.detail || "Unable to approve request", "error");
      }
    } catch (error) {
      showMessage("Failed to approve request. Please try again.", "error");
      console.error("Error approving registration request:", error);
    }
  }

  async function handleReject(event) {
    const button = event.target;
    const capability = button.getAttribute("data-capability");
    const requestId = button.getAttribute("data-request-id");

    try {
      const response = await fetch(
        `/capabilities/${encodeURIComponent(
          capability
        )}/reject?request_id=${encodeURIComponent(requestId)}`,
        {
          method: "POST",
          headers: getAuthHeaders(),
        }
      );

      const result = await response.json();
      if (response.ok) {
        showMessage(result.message, "success");
        fetchCapabilities();
      } else {
        showMessage(result.detail || "Unable to reject request", "error");
      }
    } catch (error) {
      showMessage("Failed to reject request. Please try again.", "error");
      console.error("Error rejecting registration request:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(event) {
    const button = event.target;
    const capability = button.getAttribute("data-capability");
    const email = button.getAttribute("data-email");

    try {
      const response = await fetch(
        `/capabilities/${encodeURIComponent(
          capability
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
          headers: getAuthHeaders(),
        }
      );

      const result = await response.json();

      if (response.ok) {
        showMessage(result.message, "success");

        // Refresh capabilities list to show updated consultants
        fetchCapabilities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  // Handle form submission
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const capability = document.getElementById("capability").value;

    try {
      const params = new URLSearchParams({
        email,
        requester_email: email,
      });

      const response = await fetch(
        `/capabilities/${encodeURIComponent(capability)}/register?${params.toString()}`,
        {
          method: "POST",
          headers: getAuthHeaders(),
        }
      );

      const result = await response.json();

      if (response.ok) {
        showMessage(result.message, "success");
        registerForm.reset();

        // Refresh capabilities list to show updated consultants
        fetchCapabilities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to register. Please try again.", "error");
      console.error("Error registering:", error);
    }
  });

  authButton.addEventListener("click", () => {
    loginModal.classList.remove("hidden");
  });

  cancelLoginButton.addEventListener("click", () => {
    closeLoginModal();
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    try {
      const response = await fetch(
        `/auth/login?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`,
        {
          method: "POST",
        }
      );
      const result = await response.json();

      if (!response.ok) {
        showMessage(result.detail || "Login failed", "error");
        return;
      }

      authToken = result.token;
      localStorage.setItem("authToken", authToken);
      currentUser = result.user;
      setAuthUiState();
      closeLoginModal();
      showMessage(`Signed in as ${currentUser.username}`, "success");
      fetchCapabilities();
    } catch (error) {
      showMessage("Login failed. Please try again.", "error");
      console.error("Error logging in:", error);
    }
  });

  logoutButton.addEventListener("click", async () => {
    try {
      await fetch("/auth/logout", {
        method: "POST",
        headers: getAuthHeaders(),
      });
    } catch (error) {
      console.error("Error logging out:", error);
    }

    authToken = "";
    currentUser = null;
    localStorage.removeItem("authToken");
    setAuthUiState();
    showMessage("Logged out", "info");
    fetchCapabilities();
  });

  // Initialize app
  hydrateAuth().then(fetchCapabilities);
});
