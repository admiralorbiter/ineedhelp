# ineedhelp
ineedhelp.pro Socratic CS GPT tutor for my students.

Running
python app.py

Testing
python -m pytest

**ineedhelp.pro** is a **Flask (Python) application** that integrates with OpenAI’s API for AI-driven tutoring. It uses **PostgreSQL** (with plans for a vector database) to store user data and chat history, ensuring secure, FERPA-compliant data management. The front end is built with **HTML/CSS/JavaScript** on top of **Bootstrap**, allowing for a clean, responsive UI. As usage scales, the system’s modular design supports future integrations with Redis caching, additional vector databases (e.g., Pinecone/Weaviate), and local AI models for cost optimization.

### Core Data & Architecture

- **User & Role Management**: Teacher/Student roles, daily question-limit tracking, and admin overrides.
- **Chat Data**: Secure storage of conversation logs, images, and code snippets using encryption and planned caching layers.
- **AI Integration**: **GPT-4o-mini** handles image/file analysis, while **GPT-3.5-turbo** focuses on text conversations, with advanced vector search in development.
- **Security & Compliance**: Adheres to role-based authentication, with encryption for sensitive records and best practices from OWASP.
- **Scalability**: Future-proof design for easy migration to AWS S3 for file storage, Redis for caching, and expansions in advanced analytics or collaboration features.


