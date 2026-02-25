# Distributed Drive System

A secure, scalable, and decentralized file storage solution built on a master-worker architecture using Python, Flask, and Docker. This repository contains the complete codebase for deploying and managing the distributed network over a Local Area Network (LAN).

## 1. System Architecture
The system employs a **Master-Worker** (or Master-Storage Node) architecture:

*   **Master Node (1 Instance):** The core controller. It serves the Web UI, handles user authentication, manages metadata (SQLite Database), intercepts file uploads, performs chunking and hashing, and coordinates data distribution across the network.
*   **Storage Nodes (Dynamic, Currently 5 Instances):** Workers responsible solely for raw data persistence. They receive chunks from the Master, save them to disk, and serve them back upon request. They run in a private network space and cannot be accessed directly by users.

### The Storage Principle (Chunking & Replication)
When a user uploads a file, it is not stored as a single monolith. Instead, the Master node:
1.  **Slices** the file into fixed-size `1 MB` chunks on the fly.
2.  **Hashes** each chunk using `SHA-256` to ensure data integrity.
3.  **Distributes** the chunks evenly across active Storage Nodes using a Round-Robin algorithm.
4.  **Replicates** every chunk across at least `2` different Storage Nodes to guarantee high availability even if a node crashes.

---

## 2. Core Features

### 📡 Real-time UI & Dashboard
*   **Modern Aesthetic:** A premium, fully responsive interface built with core CSS, featuring dark-mode elements, gradient hover states, and smooth micro-animations.
*   **Upload Progress Tracking:** An asynchronous file upload system using `XMLHttpRequest` tracks upload progress dynamically, displaying an interactive progress bar without freezing the UI.
*   **Local Time Conversion:** All server timestamps are stored in UTC, avoiding database conflicts. On the client side, vanilla JavaScript seamlessly converts these times to the user's localized timezone.

### 🔐 Security & Access Control
*   **Internal API Protection (JWT):** The Master and Storage nodes communicate securely using JSON Web Tokens (JWT). The Master signs a payload authorizing specific actions (e.g., `upload`, `download`), which the Storage Node verifies using a pre-shared `NODE_REGISTRATION_KEY`.
*   **Clock Drift Resolution:** To prevent distributed nodes with misaligned system clocks from rejecting tokens, a `leeway` of 24 hours (86400 seconds) is built into the JWT verification logic.
*   **Data Integrity Verification:** During downloads, the Master streams chunks from the Storage Nodes. Before transmitting each byte to the user, it recalculates the `SHA-256` hash and verifies it against the original database record to prevent corruption.

### 🛡️ Network Resilience & Monitoring
*   **Automated Node Health Monitor:** The Master runs a continuous background daemon thread (`monitor_nodes`). It interrogates the `last_heartbeat` status of all nodes every 30 seconds.
*   **Auto-failover Detection:** If a node goes offline (fails to send a POST heartbeat within 60 seconds), the Master instantly flags it as `Offline` in the database, updating the Admin Dashboard and bypassing it for future file allocations.
*   **Dynamic Node Registration:** New nodes can be booted dynamically (e.g., `docker-compose up -d storage5`). They automatically register themselves via the Master API and instantly become available for chunk allocation without requiring a Master reboot.

---

## 3. How to Document & Share This Project

To share this documentation with your project members or professors, you have chosen the best approach: **storing it directly in your version control repository**.

### Sharing the Documentation (GitHub)
The easiest and most professional way to share system operations is by committing this `README.md` file to your GitHub repository. Whenever a team member visits the project link on GitHub, this file is automatically natively rendered on the front page.

### Sharing Using PDF Generation
If your project members require offline documentation (e.g., for thesis submission), you can easily convert this Markdown file into a PDF. 
Because Windows PowerShell restricts executions through sandbox bounds occasionally, the simplest method is to use modern web tools:
1.  Open [Dillinger.io](https://dillinger.io/) or [Markdown to PDF (markdowntopdf.com)](https://markdowntopdf.com/).
2.  Copy and paste the raw text of this README.
3.  Click "Export as PDF" and share it via Google Drive, Telegram, or Email.
