// Hide the loading overlay once the entire site is loaded
window.addEventListener("load", () => {
    const overlay = document.getElementById("loading-overlay");
    if (overlay) {
        overlay.style.display = "none";
    }
});

document.getElementById("resume").addEventListener("change", async function () {
    if (!this.files.length) return;

    const formData = new FormData();
    formData.append("resume", this.files[0]);

    const resultDiv = document.getElementById("result");
    const parsedDataDiv = document.getElementById("parsed-data");

    // Display the result container and a spinner immediately
    resultDiv.style.display = "block";
    parsedDataDiv.innerHTML = `<div class="spinner"></div>`;

    try {
        const response = await fetch("/upload", {
            method: "POST",
            body: formData
        });
        const data = await response.json();
        if (data.error) {
            parsedDataDiv.innerHTML = `<p class="error">Error: ${data.error}</p>`;
        } else {
            parsedDataDiv.innerHTML = `
                <div class="section">
                    <h3>Personal Info</h3>
                    <p><span>Name:</span> ${data.name.replace(/\n/g, " ")}</p>
                    <p><span>Email:</span> ${data.email}</p>
                    <p><span>Phone:</span> ${data.phone || "Not provided"}</p>
                </div>
                <div class="section">
                    <h3>Education</h3>
                    <ul>
                        ${data.education.map(edu => `<li>${edu.degree}</li>`).join("")}
                    </ul>
                </div>
                <div class="section">
                    <h3>Work Experience</h3>
                    <ul>
                        ${data.work_experience.map(exp => `<li>${exp.description}</li>`).join("")}
                    </ul>
                </div>
                <div class="section">
                    <h3>Skills</h3>
                    <ul class="skills-list">
                        ${data.skills.map(skill => `<li>${skill}</li>`).join("")}
                    </ul>
                </div>
                ${data.ai_summary ? `<div class="section"><h3>AI Summary</h3><p>${data.ai_summary}</p></div>` : ""}
            `;
        }
    } catch (error) {
        console.error("Error:", error);
        parsedDataDiv.innerHTML = `<p class="error">An error occurred.</p>`;
    }
});