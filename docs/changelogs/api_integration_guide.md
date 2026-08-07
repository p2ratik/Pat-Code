# API Integration Guide for Frontend Engineers

This document provides a comprehensive summary of the currently implemented APIs and their request/response payloads based on the backend schema and routes. This guide should serve as a reference for building and integrating the frontend.

## Authentication (JWT-Based)

The API uses standard JSON Web Token (JWT) Bearer authentication for most endpoints.

- **Header Format:** `Authorization: Bearer <access_token>`
- **Token Generation:** Use the `/users/{user_id}/token` endpoint to generate an access token for a specific user (currently used for obtaining a token during development or after user creation).
- **Unauthorized Handling:** Endpoints requiring auth will return `401 Unauthorized` (missing/invalid/expired token) or `403 Forbidden` (disabled account or insufficient role privileges).

---

## Endpoint Reference

### 1. Chat API (`/chat`)

**POST /chat**
*Send a message to the AI agent. (Auth Required)*

- **Request Body:**
  ```json
  {
    "message": "string (Required: The user's input message)",
    "conversation_id": "string | null (Optional: Include to continue an existing conversation, leave null for a new one)"
  }
  ```
- **Response Body:**
  ```json
  {
    "conversation_id": "string (The ID of the current/new conversation)",
    "response": "string (The agent's reply)"
  }
  ```

---

### 2. Users API (`/users`)

**POST /users**
*Create a new user. (No Auth Required)*

- **Request Body:**
  ```json
  {
    "email": "string",
    "display_name": "string"
  }
  ```
- **Response Body:**
  ```json
  {
    "id": "string (UUID)",
    "email": "string",
    "display_name": "string",
    "roles": ["string"],
    "is_active": true,
    "created_at": "string (ISO 8601 Timestamp)"
  }
  ```

**GET /users/{user_id}**
*Retrieve details for a specific user. (Auth Required)*

- **Response Body:** Same as the `POST /users` response.

**POST /users/{user_id}/token**
*Generate a JWT token for the specified user. (No Auth Required)*

- **Request Body:** None
- **Response Body:**
  ```json
  {
    "access_token": "string",
    "token_type": "bearer"
  }
  ```

**POST /users/{user_id}/roles**
*Assign a role to a user. (Auth Required - Admin Only, Dev Mode Only)*

- **Request Body:**
  ```json
  {
    "role_name": "string"
  }
  ```
- **Response Body:**
  ```json
  {
    "detail": "Role '...' assigned to user ..."
  }
  ```

**GET /users/{user_id}/profile**
*Get the active agent profile assigned to a user. (Auth Required)*

- **Response Body:**
  ```json
  {
    "id": "string (UUID)",
    "name": "string",
    "description": "string | null",
    "model_name": "string",
    "temperature": 0.7,
    "max_turns": 100,
    "version": 1,
    "is_active": true,
    "prompt_id": "string (UUID) | null"
  }
  ```
  *(Returns `null` if the user has no active profile assigned)*

**POST /users/{user_id}/profile**
*Assign an agent profile to a user. (Auth Required - Admin Only, or assigning to self)*

- **Request Body:**
  ```json
  {
    "profile_id": "string (UUID of the profile)"
  }
  ```
- **Response Body:**
  ```json
  {
    "detail": "Profile assigned to user ..."
  }
  ```

---

### 3. Profiles API (`/profiles`)

**GET /profiles**
*List all active agent profiles in the system. (Auth Required)*

- **Response Body:** An array of Profile objects.
  ```json
  [
    {
      "id": "string",
      "name": "string",
      "description": "string | null",
      "model_name": "string",
      "temperature": 0.7,
      "max_turns": 100,
      "version": 1,
      "is_active": true,
      "prompt_id": "string (UUID) | null"
    }
  ]
  ```

**POST /profiles**
*Create a new agent profile. (Auth Required - Admin Only)*

- **Request Body:**
  ```json
  {
    "name": "string (Required)",
    "model_name": "string (Optional, defaults to 'gpt-4.1-mini')",
    "temperature": 0.7,
    "max_turns": 100,
    "description": "string | null (Optional)",
    "prompt_id": "string (UUID, Optional) | null"
  }
  ```
- **Response Body:** The created Profile object (same shape as above).

**GET /profiles/{profile_id}/tools**
*List all tools assigned to a specific profile. (Auth Required)*

- **Response Body:** An array of Tool objects.
  ```json
  [
    {
      "id": "string (UUID)",
      "name": "string (e.g., 'read_file')",
      "description": "string | null"
    }
  ]
  ```

**PUT /profiles/{profile_id}/tools**
*Replace the tool set for a specific profile. (Auth Required - Admin Only)*

- **Request Body:**
  ```json
  {
    "tool_names": ["string", "string"] // Provide the names of the tools, not IDs.
  }
  ```
- **Response Body:**
  ```json
  {
    "detail": "Assigned N tools to profile ..."
  }
  ```

---

### 4. Tools API (`/tools`)

**GET /tools**
*List all registered tools available in the system. (Auth Required)*

- **Response Body:** An array of Tool objects.
  ```json
  [
    {
      "id": "string (UUID)",
      "name": "string",
      "description": "string | null"
    }
  ]
  ```

---

### 5. Prompts API (`/prompts`)

Prompts are system-prompt templates that can be linked to agent profiles via `prompt_id`.
When a profile has a `prompt_id`, the agent uses that prompt as its system prompt instead
of the built-in default.

**GET /prompts**
*List all prompts. (Auth Required)*

- **Response Body:** An array of Prompt objects.
  ```json
  [
    {
      "id": "string (UUID)",
      "name": "string",
      "version": 1,
      "content": "string",
      "is_active": true,
      "created_at": "string (ISO 8601 Timestamp)"
    }
  ]
  ```

**POST /prompts**
*Create a new prompt. (Auth Required - Admin Only)*

- **Request Body:**
  ```json
  {
    "name": "string (Required)",
    "content": "string (Required)",
    "version": 1
  }
  ```
- **Response Body:** The created Prompt object.

**GET /prompts/{prompt_id}**
*Get a single prompt by ID. (Auth Required)*

- **Response Body:** A single Prompt object.

**PATCH /prompts/{prompt_id}**
*Partially update a prompt. (Auth Required - Admin Only)*

- **Request Body:** All fields optional, only provided fields are changed.
  ```json
  {
    "name": "string | null",
    "content": "string | null",
    "is_active": "boolean | null"
  }
  ```
- **Response Body:** The updated Prompt object.

---

## Suggested Frontend Data Structures (Typescript)

```typescript
export interface User {
  id: string;
  email: string;
  display_name: string;
  roles: string[];
  is_active: boolean;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface ChatMessage {
  message: string;
  conversation_id?: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  response: string;
}

export interface AgentProfile {
  id: string;
  name: string;
  description: string | null;
  model_name: string;
  temperature: number;
  max_turns: number;
  version: number;
  is_active: boolean;
  prompt_id: string | null;
}

export interface Tool {
  id: string;
  name: string;
  description: string | null;
}

export interface Prompt {
  id: string;
  name: string;
  version: number;
  content: string;
  is_active: boolean;
  created_at: string;
}
```
