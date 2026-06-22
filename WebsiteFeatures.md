# NewsMatrix System Features

This document provides a comprehensive summary of all existing features of the NewsMatrix website (excluding queues, caches, and RAG architectures for simplicity).

---

## 1. Access Control (Role-Based Access Control - RBAC)
The system is built with a strict authorization model enforced on both the Frontend (Vue Router navigation guards) and Backend (FastAPI dependencies). There are 3 main roles:
* **Admin (Administrator):** Full management access to users, organizations, article categories, and document uploads.
* **Journalist:** Permission to manage articles belonging specifically to their associated organization (create, edit, delete, publish, or revert to draft).
* **User (Regular User):** Permission to read public articles, perform social interactions (likes, comments, following organizations), and send internal messages.

---

## 2. Public Client Features

### 2.1. Homepage
* Premium Bento Box style user interface showing a neat layout of entry portals (News feed, Organizations directory, authentication links).
* Interactive image carousel displaying responsive animations with expand/collapse options.

### 2.2. News Feed
* **Published News Feed:** Lists only published articles (hides drafts). Each item card displays details such as thumbnail, title, short description, authors, category pills, and interaction counters (likes count, comments count, organization followers count).
* **Filter & Search:**
  - Search by keyword matching against article title, content, or category name.
  - Quick filtering by categories.
  - Date picker filtering based on publication date.
* **Data Sources (Multi-source Toggle):** Allows toggling the feed source dynamically:
  1. *System data:* Real production data fetched from the PostgreSQL database via backend endpoints.
  2. *Mock data:* Static mock data stored in local JSON format (`news.json`).
  3. *External data:* Calls an external news API provider (GNews API) with a 60-second caching mechanism and customizable API URL configuration in the UI.
* **Pagination:** Supports configurable page sizes (5 or 10 articles per page) and smooth navigation controls.
* **Instant Interaction:** Logged-in users can directly like/unlike articles and follow/unfollow organizations from the news feed cards.

### 2.3. News Detail Page
* Shows the full content of the news article (title, author list, publish date, body content, categories).
* **Social Actions:** Like/unlike actions and follow/unfollow organization actions (only enabled for articles that are "Published").
* **Comments Feed:**
  - View all user comments chronologically, displaying author email and timestamps.
  - Post new comments (requires a logged-in user and a published article).

### 2.4. About Page
* Core mission statements, organizational values, and product roadmap of NewsMatrix.
* **Interactive Sandbox:** Dynamic inputs demonstrating Vue's Two-way Data Binding by reacting to user's name input and image selection.

---

## 3. Journalist Workspace
A dedicated admin panel for journalists belonging to news agencies (Administrators also have access to these management features):
* **Internal Article List:** View all articles created by the journalist's organization (both Draft and Published).
* **Create New Article:** Input form for title, content, status selection (Draft / Published), and multi-select categories.
* **Edit Article:** Update details and contents of previously created articles.
* **Delete Article:** Remove articles permanently from the system (requires confirmation dialog).

---

## 4. Admin Portal

### 4.1. Organization Management
* **Organization List:** Monitor registered news organizations and their configuration limits, including daily post limits (`daily_post_limit`), daily edit limits (`current_edit_limit`), and total followers.
* **Add Organization:** Create a new workspace/organization profile with custom operational limits.
* **Edit Organization:** Update names, descriptions, and daily post/edit restrictions.
* **Delete Organization:** Completely remove organization profiles.
* **Staffing Management (Organization Detail Page):**
  - View all journalists currently working under the organization (paginated at 5 members per page).
  - Add free-agent journalists (those not currently tied to any organization).
  - Remove (dismiss) journalists from the organization.

### 4.2. Category Management
* View all available article categories sorted alphabetically.
* Create new categories (requires a unique name, cannot be empty).
* Rename existing categories.
* Delete unused categories.

### 4.3. User Governance
* Bento Box UI summarizing key user statistics (Total users, active roles, role groups).
* Directory displaying user avatars, emails, assigned roles (colored pills), and update times.
* **Create User:** Register new accounts with specific roles (User, Journalist, Admin).
* **Modify User:** Update account email, roles, or reset passwords (leaving it empty retains the old password).
* **Delete User:** Permanently remove user accounts.

### 4.4. Document Ingestion
* **PDF Upload:** Admin can upload PDF files containing domain knowledge base information.
* **Pipeline Processing:** Uploaded PDFs are stored in the Supabase Storage bucket (`raw_data`), split into smaller text chunks, and indexed into the vector database.
* **Ingestion History:** Logs of ingested documents showing file names, page counts, chunk counts, format details, storage path, and timestamps.

---

## 5. User Authentication & Security
* **User Sign Up:** Standard email registration; new users default to the "User" role.
* **Standard Sign In:** Secure authentication verifying email and password, returning a JWT token for persistent sessions.
* **Social Sign In (OAuth2):** Quick authentication using Google or GitHub (verifies email details, automatically registers a new account with the "User" role if the email is not present in the system database).
* **Logout:** Clears token credentials from the client application state and redirects to the login screen.
