# NewsMatrix Frequently Asked Questions (FAQ)

This document contains answers to common practical, everyday questions that users, journalists, and administrators may ask when interacting with the NewsMatrix platform.

---

## 1. Reader & General User FAQ (News Feed, Likes, Comments, & Filters)

### How do I switch the homepage news feed source from static mock data to real production or external news?
The NewsMatrix homepage features a **Multi-source Toggle** located in the News Feed section. You can dynamically switch between three data sources:
1. **System data:** Fetches real production database data served via backend APIs.
2. **Mock data:** Reads static mock data from a local JSON file (`news.json`).
3. **External data:** Calls the GNews API to fetch international articles, which includes a 60-second caching mechanism and customizable API URLs.

### Why am I unable to like articles or write comments under a news post?
To like articles or post comments, you must meet the following two requirements:
1. **Authentication:** You must be logged in to a valid account (either via standard email/password credentials or Google/GitHub OAuth2).
2. **Article Status:** The article must be in the `Published` state. Likes and comments are disabled for articles that are still in `Draft` mode.

### How do I follow or unfollow a news organization/agency on NewsMatrix?
Logged-in users can follow or unfollow a news agency in two ways:
1. Directly from the organization's info card on the News Feed page.
2. From the News Detail Page of an article written by that organization.
Clicking the "Follow" button increments the organization's follower count, which is cached in Redis for instant feedback and synced asynchronously via RabbitMQ to the main PostgreSQL database.

### How do I search for articles published within a specific date range or week?
On the News Feed page, use the built-in **Date Picker** filter. You can select a start date and an end date to filter and display only the articles that were officially published during that period.

### How does the search bar work? Can I search inside the article body content?
Yes, the search functionality supports full-text search. Entering keywords in the search bar matches them against the article's title, body content, and associated category names.

### Can I change the number of articles displayed on each page of the news feed?
Yes. The news feed implements pagination, allowing you to select a page size of either **5 or 10 articles** per page using the pagination dropdown in the feed footer.

### How do I use the interactive carousel on the homepage?
The homepage features an interactive image carousel. You can hover over it to pause animations, use navigation arrows to switch slides, and click the expand/collapse option to view details.

### What is the Two-Way Data Binding sandbox on the About page?
The About page includes an interactive developer sandbox designed to demonstrate Vue 3's two-way data binding reactivity. When you type in the name input field or select a demo image, the UI instantly reacts and updates the displayed state without reloading the page.

---

## 2. Account Registration, Roles & Permissions FAQ

### How do I sign up for an account on NewsMatrix?
You can sign up using the standard Sign Up form by providing your email and password. By default, newly registered accounts are assigned the **User** (Regular User) role.

### Can I log in using my Google or GitHub account?
Yes. NewsMatrix supports Social Sign In via OAuth2 for both **Google** and **GitHub**. If you log in with a social account that doesn't exist in the database yet, the system will automatically register a new account for your email address with the default **User** role.

### Do regular users have permission to write and publish news articles?
No. Under the Role-Based Access Control (RBAC) model, only users with the **Journalist** or **Admin** roles can access the workspaces required to write, edit, and publish articles.

### How can I change my password or update my account details?
Users can manage their account details through their profile settings. Administrators can also update user emails, assign roles, or trigger a password reset through the **User Governance** portal in the Admin Dashboard.

### Why can't I access the Journalist Workspace after signing in?
Access to the Journalist Workspace is protected by Vue Router navigation guards on the frontend and FastAPI dependency injection on the backend. If your account's role is **User**, you do not have permission to view or call journalist endpoints. If you are a journalist, please contact the site administrator to upgrade your account role.

---

## 3. Journalist & Editing Workflows FAQ

### How do I save an article as a Draft instead of publishing it immediately?
When creating or editing an article in the Journalist Workspace, the form provides a status selection dropdown. To save it without displaying it on the public news feed, select the **Draft** status. When you are ready to make it public, change the status to **Published**.

### How do I permanently delete an article I created?
In the Journalist Workspace's internal article catalog, click the "Delete" button next to the target article. A confirmation modal dialog will pop up to prevent accidental deletion. Confirming the deletion removes the article permanently from the database.

### Why am I receiving an error saying "Daily Post Limit Exceeded" or "Edit Limit Exceeded" when managing articles?
To prevent database spam, each news organization has specific operational quotas configured by the Administrator. If you reach your organization's `daily_post_limit` (number of new articles created in a day) or `current_edit_limit` (number of edits allowed in a day), the backend API will block further operations until the daily quota resets.

### Can an article have multiple co-authors?
Yes. The database schema supports a many-to-many relationship between articles and authors (journalists). When creating or editing an article, you can select and tag multiple journalists as co-authors.

---

## 4. System Administration & AI Document Ingestion FAQ

### How do I change a user's role from User to Journalist?
An Administrator can change user roles by going to the **Admin Portal -> User Governance**. Locate the user in the directory, click edit, select the new role (e.g., `Journalist`), and assign them to their corresponding organization.

### How do I upload PDF documents to the AI Assistant's knowledge base?
Administrators can upload documents via the **Document Ingestion** panel in the Admin Portal. Uploaded PDFs are stored in the Supabase Storage `raw_data` bucket, automatically parsed, split into text chunks, converted into 1536-dimensional embeddings, and saved in the PostgreSQL vector database (`pgvector`).

### Where can I monitor the status of uploaded PDFs and check for processing errors?
The Document Ingestion dashboard displays the **Ingestion History** log. This log tracks every processed document, showing the file name, page counts, generated chunk counts, file format, Supabase storage path, and timestamps, allowing admins to verify successful ingestion.

### What happens to journalists when their associated News Organization is deleted?
If an Administrator deletes a news organization, the system preserves the journalist accounts but removes their association. They become "free agents" (journalists not currently tied to any organization) and can be reassigned to other organizations in the Staffing Management dashboard.

### How does the system handle high-volume interactions like sudden spikes in Likes or Comments?
NewsMatrix uses a Message Queue (RabbitMQ) and Caching (Redis) architecture. When a user likes an article, the event is immediately cached in Redis for fast frontend rendering, and a message is pushed to the RabbitMQ queue. An asynchronous background worker consumes these messages one by one to update the PostgreSQL database, protecting it from sudden traffic spikes.
