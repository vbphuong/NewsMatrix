# NewsMatrix Detailed Features

This document provides a comprehensive breakdown of all features in **NewsMatrix**, including access control, public features, journalist workflows, admin portals, and authentication systems.

---

## 1. Access Control (Role-Based Access Control - RBAC)

The security model is implemented consistently across the stack:
- **Frontend (Vue Router Guards):** Prevents unauthorized route navigation based on roles stored in the active session.
- **Backend (FastAPI Dependencies):** Inspects JWT claims in the incoming `Authorization` header. If authorization fails, it returns a `403 Forbidden` error.

Roles:
* **Admin (Administrator):** Manages user accounts, configures news organizations, structures article categories, and uploads documents for RAG processing.
* **Journalist:** Manages articles belonging to their specific organization. Permissions include drafting, publishing, editing, and deleting articles.
* **User (Regular User):** Reads public news, likes articles, comments on published pieces, follows news agencies, and sends messages via Inbox.

---

## 2. Public Client Features

### 2.1. Homepage
- Styled as a premium Bento Box layout, linking to the News Feed, Organizations directory, and authentication portals.
- Integrates an interactive photo carousel with responsive preview effects.

### 2.2. News Feed
* **Published News Feed:** Restricts listing to `Published` articles, hiding drafts. Cards display titles, summaries, lists of authors, categories, and interaction counters (likes count, comments count, followers count).
* **Search & Filters:**
  - Full-text search across titles, contents, and categories.
  - Quick-filters by category selection.
  - Date range filters to retrieve articles published on specific days.
* **Multi-source Toggle:** Users can switch the data source dynamically:
  1. *System data:* Real production database data served via Backend APIs.
  2. *Mock data:* Static mock data read from local JSON files (`news.json`).
  3. *External data:* Calls GNews API. Implements a 60-second caching mechanism and customizable API URLs.
* **Pagination:** User-controlled page sizes (5 or 10 articles) with easy page-flipping controls.
* **Feed Interactions:** Logged-in users can like/unlike and follow/unfollow organizations directly from the feed card.

### 2.3. News Detail Page
* Displays full content alongside author details, publication date, and category pills.
* **Asynchronous Comments:**
  - Chronological list of user comments with sender emails and timestamps.
  - Post comments asynchronously using RabbitMQ queues to guarantee high throughput and minimize blocking.
* **Likes & Follows:** Real-time updates for like counters and followed news agencies.

### 2.4. About Page
- Details core mission goals and development roadmap milestones.
- Toggles an interactive Vue sandbox demonstrating Two-Way Data Binding using user inputs.

---

## 3. Journalist Workspace

Journalists are greeted with a dedicated workspace dashboard upon signing in:
* **Organization Catalog:** View all articles created by the journalist's organization (both Draft and Published).
* **Create Article:** Form inputs for title, content, status selection, and category tagging.
* **Edit Article:** Update existing articles. The system validates the organization's edit quota (`current_edit_limit`) to restrict excessive edits.
* **Delete Article:** Permanently delete articles after confirming with a modal check.

---

## 4. Admin Portal

### 4.1. Organization Management
* **Overview Dashboard:** List news organizations, showing daily limits (`daily_post_limit`), editing limits (`current_edit_limit`), and total followers.
* **Create/Update Organizations:** Initialize or configure news organizations.
* **Staff Management (Organization Detail Page):**
  - List journalists working under the organization (paginated at 5 per page).
  - Add free-agent journalists to the organization.
  - Remove (dismiss) journalists from the organization.

### 4.2. Category Management
* List all categories alphabetically.
* Create new categories (guarantees unique, non-empty names).
* Update category names and delete unused categories.

### 4.3. User Governance
* Bento Box visual metrics tracking user counts and active roles.
* Detailed user list showing emails, assigned roles (colored badges), and updates.
* Register new accounts, update roles, reset passwords, or delete accounts.

### 4.4. Document Ingestion
- **PDF Upload:** Admin uploads knowledge base PDF documents.
- **Auto-Pipeline:** Triggers Supabase Storage transfers, chunking, and database indexing.
- **Ingestion Log:** Monitors ingested PDFs, showing page counts, chunk counts, files formats, paths, and timestamps.

---

## 5. User Authentication & Security

* **User Sign Up:** Account creation with email and password, default role set to `User`.
* **Standard Sign In:** Standard credential check, returning a JWT token for authorization headers.
* **Social Sign In (OAuth2):** Login via Google or GitHub. If the account email is not in the system, it automatically registers a new account under the `User` role.
* **Logout:** Clears token storage and redirects to the login screen.
